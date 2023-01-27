# pylint: disable = C0103, R0902, W1203, C0301

import json
import logging
import traceback
import os
import boto3
import botocore
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
logger.setLevel(logging.INFO)

######################################################################
#                        CLASS DEFINITION                            #
######################################################################


class TagReplicator:
    """
    TagReplicator Controller class. Handles all resource operations and logic.
    """

    # INIT
    def __init__(self, event, context):
        """
        Initialization function. Sets all the environment variables and default values
        """
        self.sts_client = boto3.client('sts')
        self.session_id = boto3.session.Session().client('sts').get_caller_identity()
        self.account_id = boto3.client('sts').get_caller_identity()['Account']
        logger.info(f'got account: {self.account_id}')
        self.deployment_region = boto3.session.Session().region_name
        self.function_arn = context.invoked_function_arn

        self.tags_to_exclude_when_copying = 'aws:backup:source-resource'
        self.tags_to_exclude_when_copying = self.tags_to_exclude_when_copying.split(',')



    def parse_arn(self,arn):
        """
        Helper function to parse an ARN
        """

        elements = arn.split(':', 5)
        result = {
            'arn': elements[0],
            'partition': elements[1],
            'service': elements[2],
            'region': elements[3],
            'account': elements[4],
            'resource': elements[5],
            'resource_type': None
        }
        if '/' in result['resource']:
            result['resource_type'], result['resource'] = result['resource'].split('/',1)
        elif ':' in result['resource']:
            result['resource_type'], result['resource'] = result['resource'].split(':',1)
        return result

    def get_resource_id_from_arn(self, resource_arn):
        """
        Helper function to get the ResourceId from a given Arn.
        """
        # "ResourceArn":"arn:aws:ec2:{RegionId}:{AccountId}:volume/{VolumeId}"
        if -1 != resource_arn.find('/'):
            # Handle for EC2 and EBS
            resource_id = resource_arn.split("/")[1]
        elif -1 != resource_arn.find(':::'):
            # Handle for S3
            resource_id = resource_arn.split(":::")[1]
        else:
            resource_id = resource_arn
        return resource_id

    def __set_tags_by_resource(self, resource_type, resource_id, resource_arn, tag_list):
        """
        Helper function to set the tags on a given resource.
        """
        resource_type = resource_type.lower()
        logger.info(f"Processing __set_tags_by_resource with resource_type: {resource_type}, " +
             f"resource_arn : {resource_arn},resource_id : {resource_id}, tag_list : {tag_list}" +
             f"tag exclusions : {self.tags_to_exclude_when_copying}")


        for tag_info in tag_list:
            if tag_info['Key'] in self.tags_to_exclude_when_copying:
                tag_list.remove(tag_info)

        if resource_type in ('rds', 'aurora'):
            rds_client = boto3.client('rds')
            rds_client.add_tags_to_resource(ResourceName=resource_id, Tags=tag_list)

        elif resource_type in ('ec2', 'ebs'):
            ec2_client = boto3.client('ec2')
            ec2_client.create_tags(DryRun=False, Resources=[resource_id], Tags=tag_list)

        else:
            logger.info(f"{resource_type} Not Supported Yet, Fetchable from backup")

    def __get_tags_by_resource(self, resource_type, resource_arn, recovery_point_arn):
        """
        Helper function to get Tags for a given resource detail
        """
        logger.info(f"__get_tags_by_resource resource_type {resource_type}, " +
             f"resourceArn : {resource_arn}, recovery_point_arn : {recovery_point_arn}")

        resource_id = self.get_resource_id_from_arn(resource_arn)

        resource_tag_list = {}
        recovery_point_tag_list = {}
        resource_type = resource_type.lower()
        backup_client = boto3.client('backup')

        try:

                recovery_point_tag_list = backup_client.list_tags(ResourceArn=recovery_point_arn)
                if 'ResponseMetadata' in recovery_point_tag_list:
                    del recovery_point_tag_list['ResponseMetadata']

        except botocore.exceptions.ClientError as e:
                logger.error(f"{e.response['Error']}")

        try:
            resource_tag_list = self.get_resource_tags(resource_type,resource_id,resource_arn)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "ResourceNotFoundException": 
                #Try to get the tags from the recovery point
                logger.error(f"Resource not fouund. Falling back to recovery_point_arn")

        if not 'Tags' in resource_tag_list or len(resource_tag_list['Tags']) == 0:
            logger.info('No tags extracted from original resource. Attempting tag extraction from recovery_point_arn')
            resource_id = self.get_resource_id_from_arn(recovery_point_arn)
            resource_tag_list = self.get_resource_tags(resource_type,resource_id,resource_arn)

        if 'ResponseMetadata' in resource_tag_list:
            del resource_tag_list['ResponseMetadata']

        name_exist = False
        for tag_info in resource_tag_list['Tags']:
            if tag_info['Key'] == 'Name':
                name_exist = True

            if 'ResourceId' in tag_info:
                del tag_info['ResourceId']

            if 'ResourceType' in tag_info:
                del tag_info['ResourceType']

        if not name_exist:
            # Handle RDS Naming arn:aws:rds:*:*:db:{DBName}
            resource_id = resource_id.split(':')[-1]
            # Handle instance/{InstanceId}
            resource_id = resource_id.split('/')[-1]
            logger.info(f"Name Tag not Found.Adding Name Tag with ResourceId : {resource_id}")
            tag_info = {'Key': 'Name', 'Value': resource_id}
            resource_tag_list['Tags'].append(tag_info)

        try:
            if 'Tags' in recovery_point_tag_list:
                # Merge the tags - From resource and Recovery point
                for recovery_point_tag_key, recovery_point_tag_value in \
                        recovery_point_tag_list['Tags'].items():
                    logger.info(
                        f"Appending recovery point Tags : {recovery_point_tag_key},{recovery_point_tag_value} to tags : {resource_tag_list['Tags']} ")
                    resource_tag_list['Tags'].append(
                        {'Key': recovery_point_tag_key, 'Value': recovery_point_tag_value})

        except Exception as e:
            logger.error(f"Error merging tags : {e}")
            var = traceback.format_exc()
            logger.error(f"Error {var} processing Merge the tags from resource and Recovery point")

        logger.info(f"__get_tags_by_resource, Resource Tag List : {resource_tag_list['Tags']}")
        return resource_tag_list

    def get_resource_tags(self,resource_type,resource_id,resource_arn):
        """
        Helper function to get Tags for a given resource detail
        """
        logger.info(f"Getting resoruce tags for type : {resource_type} with Id : {resource_id} under ARN : {resource_arn}")
        if resource_type in ('rds', 'aurora'):
            rds = boto3.client('rds')
            resource_tag_list = rds.list_tags_for_resource(ResourceName=resource_id)

            # Return is different from other resources. Unify the section
            resource_tag_list['Tags'] = resource_tag_list.pop('TagList')

        elif resource_type in ('ec2', 'ebs'):
            # Extract resource tag from the resource Arn
            ec2 = boto3.client('ec2')
            resource_tag_list = ec2.describe_tags(
                Filters=[
                    {
                        'Name': 'resource-id',
                        'Values': [
                            resource_id
                        ]
                    },
                ],
            )

            logger.info(f'ec2 resource_tag_list : {resource_tag_list}')

        else:
            logger.info(f"{resource_type} Not Supported Yet, Fetchable from backup")

        return resource_tag_list

    def handle_restore_event_data(self, job_id):
        """
        Helper function to write the Restore Job Event data
        """
        logger.info(f"Processing handle_restore_event_data with jobId : {job_id}")

        backup_client = boto3.client('backup')
        restore_info = backup_client.describe_restore_job(RestoreJobId=job_id)
        if 'ResponseMetadata' in restore_info:
            del restore_info['ResponseMetadata']

        backup_client = boto3.client('backup')
        backupvault_list = backup_client.list_backup_vaults(MaxResults=100)

        recovery_info = []
        for backupVaultInfo in backupvault_list['BackupVaultList']:
            backup_vault_name = backupVaultInfo['BackupVaultName']
            recovery_point_arn = restore_info['RecoveryPointArn']
            try:
                # Figure out the backup details
                recovery_info = backup_client.describe_recovery_point(
                    BackupVaultName=backup_vault_name,
                    RecoveryPointArn=recovery_point_arn
                )

                if 'ResponseMetadata' in recovery_info:
                    del recovery_info['ResponseMetadata']
                # Break since information is already found
                break
            except botocore.exceptions.ClientError as e:
                if e.response['Error']['Code'] == "ResourceNotFoundException":
                    logger.info(
                        f"Recovery Point ARN : {recovery_point_arn} not found in Vault : {backup_vault_name}")
                else:
                   logger.error(f"Error : {e} processing describe_recovery_point")

        create_resource_arn = restore_info.get('CreatedResourceArn')
        if create_resource_arn:
            try:
                resource_arn = recovery_info.get('ResourceArn')
                resource_type = recovery_info.get('ResourceType')
                recovery_point_arn = recovery_info.get('RecoveryPointArn')
                tag_list = self.__get_tags_by_resource(resource_type, resource_arn,recovery_point_arn)

                created_resource_id = self.get_resource_id_from_arn(create_resource_arn)
                # Copy this tag list to target resource
                self.__set_tags_by_resource(resource_type, created_resource_id, create_resource_arn,
                                            tag_list['Tags'])

            except Exception as e:
                logger.error(f"Error : {e} processing __set_tags_by_resource")

    def refresh_tags_for_existing_restore_jobs(self, event):
        backup_client = boto3.client('backup')

        try:
            restore_jobs_list = backup_client.list_restore_jobs()

            for restoreJobInfo in restore_jobs_list['RestoreJobs']:
                self.handle_restore_event_data(restoreJobInfo['RestoreJobId'])

        except (ClientError, Exception):
            var = traceback.format_exc()
            logger.error(f"Error {var} n handle_refresh_job_logs")


    def handle_aws_backup_event(self, event):
        detail_type = event.get('detail-type')
        event_detail = event.get('detail')
        job_event_state = event_detail.get('state')
        if not job_event_state:
            # Hack
            job_event_state = event_detail.get('status')

        if job_event_state in ('ABORTED', 'COMPLETED', 'FAILED', 'EXPIRED'):
            if detail_type == 'Restore Job State Change':
                job_event_type = 'restore_job'
                job_id = event_detail.get('restoreJobId')
                if job_event_state in ('COMPLETED'):
                    self.handle_restore_event_data(job_id)
            else:
                logger.error(f"Skipping processing for type : {detail_type} for aws.backup")
                return

            logger.info(
                f"Processed Event Type : {job_event_type} , Event State : {job_event_state},  Job Id : {job_id}")
        else:
            logger.info(f"Ignore processing job with a status : {job_event_state}")

######################################################################


#                        FUNCTIONAL LOGIC                            #
######################################################################

def handler(event, context):
    """
    Entry point for the Lambda function.
    """
    logger.info(f'Event : {event}')
    tag_replicator = TagReplicator(event, context)

    if event.get('source') == 'aws.backup':
        try:
            tag_replicator.handle_aws_backup_event(event)
        except Exception:
            var = traceback.format_exc()
            logger.error(f"Error {var} in handle_aws_backup_event")

    elif event.get('RefreshTagItems') == 'true':
        logger.info('RefreshTagItems request')
        try:
            tag_replicator.refresh_tags_for_existing_restore_jobs(event)
        except Exception:
            var = traceback.format_exc()
            logger.error(f"Error {var} in refresh_tags_for_existing_restore_jobs")

