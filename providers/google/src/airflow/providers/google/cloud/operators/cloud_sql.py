#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""This module contains Google Cloud SQL operators."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from contextlib import contextmanager
from functools import cached_property
from typing import TYPE_CHECKING, Any

from googleapiclient.errors import HttpError

from airflow.configuration import conf
from airflow.exceptions import AirflowException
from airflow.providers.google.cloud.hooks.cloud_sql import CloudSQLDatabaseHook, CloudSQLHook
from airflow.providers.google.cloud.links.cloud_sql import CloudSQLInstanceDatabaseLink, CloudSQLInstanceLink
from airflow.providers.google.cloud.operators.cloud_base import GoogleCloudBaseOperator
from airflow.providers.google.cloud.triggers.cloud_sql import CloudSQLExportTrigger
from airflow.providers.google.cloud.utils.field_validator import GcpBodyFieldValidator
from airflow.providers.google.common.hooks.base_google import PROVIDE_PROJECT_ID, get_field
from airflow.providers.google.common.links.storage import FileDetailsLink
from airflow.providers.google.version_compat import BaseHook

if TYPE_CHECKING:
    from airflow.models import Connection
    from airflow.providers.openlineage.extractors import OperatorLineage
    from airflow.utils.context import Context


SETTINGS = "settings"
SETTINGS_VERSION = "settingsVersion"

CLOUD_SQL_CREATE_VALIDATION: Sequence[dict] = [
    {"name": "name", "allow_empty": False},
    {
        "name": "settings",
        "type": "dict",
        "fields": [
            {"name": "tier", "allow_empty": False},
            {
                "name": "backupConfiguration",
                "type": "dict",
                "fields": [
                    {"name": "binaryLogEnabled", "optional": True},
                    {"name": "enabled", "optional": True},
                    {"name": "replicationLogArchivingEnabled", "optional": True},
                    {"name": "startTime", "allow_empty": False, "optional": True},
                ],
                "optional": True,
            },
            {"name": "activationPolicy", "allow_empty": False, "optional": True},
            {"name": "authorizedGaeApplications", "type": "list", "optional": True},
            {"name": "crashSafeReplicationEnabled", "optional": True},
            {"name": "dataDiskSizeGb", "optional": True},
            {"name": "dataDiskType", "allow_empty": False, "optional": True},
            {"name": "databaseFlags", "type": "list", "optional": True},
            {
                "name": "ipConfiguration",
                "type": "dict",
                "fields": [
                    {
                        "name": "authorizedNetworks",
                        "type": "list",
                        "fields": [
                            {"name": "expirationTime", "optional": True},
                            {"name": "name", "allow_empty": False, "optional": True},
                            {"name": "value", "allow_empty": False, "optional": True},
                        ],
                        "optional": True,
                    },
                    {"name": "ipv4Enabled", "optional": True},
                    {"name": "privateNetwork", "allow_empty": False, "optional": True},
                    {"name": "requireSsl", "optional": True},
                ],
                "optional": True,
            },
            {
                "name": "locationPreference",
                "type": "dict",
                "fields": [
                    {"name": "followGaeApplication", "allow_empty": False, "optional": True},
                    {"name": "zone", "allow_empty": False, "optional": True},
                ],
                "optional": True,
            },
            {
                "name": "maintenanceWindow",
                "type": "dict",
                "fields": [
                    {"name": "hour", "optional": True},
                    {"name": "day", "optional": True},
                    {"name": "updateTrack", "allow_empty": False, "optional": True},
                ],
                "optional": True,
            },
            {"name": "pricingPlan", "allow_empty": False, "optional": True},
            {"name": "replicationType", "allow_empty": False, "optional": True},
            {"name": "storageAutoResize", "optional": True},
            {"name": "storageAutoResizeLimit", "optional": True},
            {"name": "userLabels", "type": "dict", "optional": True},
        ],
    },
    {"name": "databaseVersion", "allow_empty": False, "optional": True},
    {
        "name": "failoverReplica",
        "type": "dict",
        "fields": [{"name": "name", "allow_empty": False}],
        "optional": True,
    },
    {"name": "masterInstanceName", "allow_empty": False, "optional": True},
    {"name": "onPremisesConfiguration", "type": "dict", "optional": True},
    {"name": "region", "allow_empty": False, "optional": True},
    {
        "name": "replicaConfiguration",
        "type": "dict",
        "fields": [
            {"name": "failoverTarget", "optional": True},
            {
                "name": "mysqlReplicaConfiguration",
                "type": "dict",
                "fields": [
                    {"name": "caCertificate", "allow_empty": False, "optional": True},
                    {"name": "clientCertificate", "allow_empty": False, "optional": True},
                    {"name": "clientKey", "allow_empty": False, "optional": True},
                    {"name": "connectRetryInterval", "optional": True},
                    {"name": "dumpFilePath", "allow_empty": False, "optional": True},
                    {"name": "masterHeartbeatPeriod", "optional": True},
                    {"name": "password", "allow_empty": False, "optional": True},
                    {"name": "sslCipher", "allow_empty": False, "optional": True},
                    {"name": "username", "allow_empty": False, "optional": True},
                    {"name": "verifyServerCertificate", "optional": True},
                ],
                "optional": True,
            },
        ],
        "optional": True,
    },
]
CLOUD_SQL_EXPORT_VALIDATION = [
    {
        "name": "exportContext",
        "type": "dict",
        "fields": [
            {"name": "fileType", "allow_empty": False},
            {"name": "uri", "allow_empty": False},
            {"name": "databases", "optional": True, "type": "list"},
            {
                "name": "sqlExportOptions",
                "type": "dict",
                "optional": True,
                "fields": [
                    {"name": "tables", "optional": True, "type": "list"},
                    {"name": "schemaOnly", "optional": True},
                    {
                        "name": "mysqlExportOptions",
                        "type": "dict",
                        "optional": True,
                        "fields": [{"name": "masterData"}],
                    },
                ],
            },
            {
                "name": "csvExportOptions",
                "type": "dict",
                "optional": True,
                "fields": [
                    {"name": "selectQuery"},
                    {"name": "escapeCharacter", "optional": True},
                    {"name": "quoteCharacter", "optional": True},
                    {"name": "fieldsTerminatedBy", "optional": True},
                    {"name": "linesTerminatedBy", "optional": True},
                ],
            },
            {"name": "offload", "optional": True},
        ],
    }
]
CLOUD_SQL_IMPORT_VALIDATION = [
    {
        "name": "importContext",
        "type": "dict",
        "fields": [
            {"name": "fileType", "allow_empty": False},
            {"name": "uri", "allow_empty": False},
            {"name": "database", "optional": True, "allow_empty": False},
            {"name": "importUser", "optional": True},
            {
                "name": "csvImportOptions",
                "type": "dict",
                "optional": True,
                "fields": [{"name": "table"}, {"name": "columns", "type": "list", "optional": True}],
            },
        ],
    }
]
CLOUD_SQL_DATABASE_CREATE_VALIDATION = [
    {"name": "instance", "allow_empty": False},
    {"name": "name", "allow_empty": False},
    {"name": "project", "allow_empty": False},
]
CLOUD_SQL_DATABASE_PATCH_VALIDATION = [
    {"name": "instance", "optional": True},
    {"name": "name", "optional": True},
    {"name": "project", "optional": True},
    {"name": "etag", "optional": True},
    {"name": "charset", "optional": True},
    {"name": "collation", "optional": True},
]


class CloudSQLBaseOperator(GoogleCloudBaseOperator):
    """
    Abstract base operator for Google Cloud SQL operators.

    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param project_id: Optional, Google Cloud Project ID.  f set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    def __init__(
        self,
        *,
        instance: str,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.project_id = project_id
        self.instance = instance
        self.gcp_conn_id = gcp_conn_id
        self.api_version = api_version
        self.impersonation_chain = impersonation_chain
        self._validate_inputs()
        super().__init__(**kwargs)

    def _validate_inputs(self) -> None:
        if self.project_id == "":
            raise AirflowException("The required parameter 'project_id' is empty")
        if not self.instance:
            raise AirflowException("The required parameter 'instance' is empty or None")

    def _check_if_instance_exists(self, instance, hook: CloudSQLHook) -> dict | bool:
        try:
            return hook.get_instance(project_id=self.project_id, instance=instance)
        except HttpError as e:
            status = e.resp.status
            if status == 404:
                return False
            raise e

    def _check_if_db_exists(self, db_name, hook: CloudSQLHook) -> dict | bool:
        try:
            return hook.get_database(project_id=self.project_id, instance=self.instance, database=db_name)
        except HttpError as e:
            status = e.resp.status
            if status == 404:
                return False
            raise e

    @property
    def extra_links_params(self) -> dict[str, Any]:
        return {
            "instance": self.instance,
        }

    def execute(self, context: Context):
        pass

    @staticmethod
    def _get_settings_version(instance):
        return instance.get(SETTINGS).get(SETTINGS_VERSION)


class CloudSQLCreateInstanceOperator(CloudSQLBaseOperator):
    """
    Create a new Cloud SQL instance.

    If an instance with the same name exists, no action will be taken and
    the operator will succeed.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLCreateInstanceOperator`

    :param body: Body required by the Cloud SQL insert API, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/insert
        #request-body
    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param validate_body: True if body should be validated, False otherwise.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_create_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_create_template_fields]
    ui_color = "#FADBDA"
    operator_extra_links = (CloudSQLInstanceLink(),)

    def __init__(
        self,
        *,
        body: dict,
        instance: str,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        validate_body: bool = True,
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.body = body
        self.validate_body = validate_body
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")

    def _validate_body_fields(self) -> None:
        if self.validate_body:
            GcpBodyFieldValidator(CLOUD_SQL_CREATE_VALIDATION, api_version=self.api_version).validate(
                self.body
            )

    def execute(self, context: Context) -> None:
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        self._validate_body_fields()
        if not self._check_if_instance_exists(self.instance, hook):
            hook.create_instance(project_id=self.project_id, body=self.body)
        else:
            self.log.info("Cloud SQL instance with ID %s already exists. Aborting create.", self.instance)

        CloudSQLInstanceLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )

        instance_resource = hook.get_instance(project_id=self.project_id, instance=self.instance)
        service_account_email = instance_resource["serviceAccountEmailAddress"]
        task_instance = context["task_instance"]
        task_instance.xcom_push(key="service_account_email", value=service_account_email)


class CloudSQLInstancePatchOperator(CloudSQLBaseOperator):
    """
    Update settings of a Cloud SQL instance.

    Caution: This is a partial update, so only included values for the settings will be
    updated.

    In the request body, supply the relevant portions of an instance resource, according
    to the rules of patch semantics.
    https://cloud.google.com/sql/docs/mysql/admin-api/how-tos/performance#patch

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLInstancePatchOperator`

    :param body: Body required by the Cloud SQL patch API, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/patch#request-body
    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param project_id: Optional, Google Cloud Project ID.  If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_patch_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_patch_template_fields]
    ui_color = "#FBDAC8"
    operator_extra_links = (CloudSQLInstanceLink(),)

    def __init__(
        self,
        *,
        body: dict,
        instance: str,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.body = body
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")

    def execute(self, context: Context):
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        if not self._check_if_instance_exists(self.instance, hook):
            raise AirflowException(
                f"Cloud SQL instance with ID {self.instance} does not exist. "
                "Please specify another instance to patch."
            )
        CloudSQLInstanceLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )

        return hook.patch_instance(project_id=self.project_id, body=self.body, instance=self.instance)


class CloudSQLDeleteInstanceOperator(CloudSQLBaseOperator):
    """
    Delete a Cloud SQL instance.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLDeleteInstanceOperator`

    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_delete_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_delete_template_fields]
    ui_color = "#FEECD2"

    def execute(self, context: Context) -> bool | None:
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        if not self._check_if_instance_exists(self.instance, hook):
            print(f"Cloud SQL instance with ID {self.instance} does not exist. Aborting delete.")
            return True
        return hook.delete_instance(project_id=self.project_id, instance=self.instance)


class CloudSQLCloneInstanceOperator(CloudSQLBaseOperator):
    """
    Clone an instance to a target instance.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLCloneInstanceOperator`

    :param instance: Database instance ID to be cloned. This does not include the
            project ID.
    :param destination_instance_name: Database instance ID to be created. This does not include the
        project ID.
    :param clone_context: additional clone_context parameters as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/rest/v1/instances/clone
    :param project_id: Project ID of the project that contains the instance. If set
        to None or missing, the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_clone_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "destination_instance_name",
        "gcp_conn_id",
        "api_version",
    )
    # [END gcp_sql_clone_template_fields]

    def __init__(
        self,
        *,
        instance: str,
        destination_instance_name: str,
        clone_context: dict | None = None,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.destination_instance_name = destination_instance_name
        self.clone_context = clone_context or {}
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.destination_instance_name:
            raise AirflowException("The required parameter 'destination_instance_name' is empty or None")

    def execute(self, context: Context):
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        if not self._check_if_instance_exists(self.instance, hook):
            raise AirflowException(
                f"Cloud SQL instance with ID {self.instance} does not exist. "
                "Please specify another instance to patch."
            )
        body = {
            "cloneContext": {
                "kind": "sql#cloneContext",
                "destinationInstanceName": self.destination_instance_name,
                **self.clone_context,
            }
        }
        return hook.clone_instance(
            project_id=self.project_id,
            body=body,
            instance=self.instance,
        )


class CloudSQLCreateInstanceDatabaseOperator(CloudSQLBaseOperator):
    """
    Create a new database inside a Cloud SQL instance.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLCreateInstanceDatabaseOperator`

    :param instance: Database instance ID. This does not include the project ID.
    :param body: The request body, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/databases/insert#request-body
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param validate_body: Whether the body should be validated. Defaults to True.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_db_create_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_db_create_template_fields]
    ui_color = "#FFFCDB"
    operator_extra_links = (CloudSQLInstanceDatabaseLink(),)

    def __init__(
        self,
        *,
        instance: str,
        body: dict,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        validate_body: bool = True,
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.body = body
        self.validate_body = validate_body
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")

    def _validate_body_fields(self) -> None:
        if self.validate_body:
            GcpBodyFieldValidator(
                CLOUD_SQL_DATABASE_CREATE_VALIDATION, api_version=self.api_version
            ).validate(self.body)

    def execute(self, context: Context) -> bool | None:
        self._validate_body_fields()
        database = self.body.get("name")
        if not database:
            self.log.error(
                "Body doesn't contain 'name'. Cannot check if the"
                " database already exists in the instance %s.",
                self.instance,
            )
            return False
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        CloudSQLInstanceDatabaseLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )
        if self._check_if_db_exists(database, hook):
            self.log.info(
                "Cloud SQL instance with ID %s already contains database '%s'. Aborting database insert.",
                self.instance,
                database,
            )
            return True
        return hook.create_database(project_id=self.project_id, instance=self.instance, body=self.body)


class CloudSQLPatchInstanceDatabaseOperator(CloudSQLBaseOperator):
    """
    Update resource containing information about a database using patch semantics.

    See: https://cloud.google.com/sql/docs/mysql/admin-api/how-tos/performance#patch

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLPatchInstanceDatabaseOperator`

    :param instance: Database instance ID. This does not include the project ID.
    :param database: Name of the database to be updated in the instance.
    :param body: The request body, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/databases/patch#request-body
    :param project_id: Optional, Google Cloud Project ID.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param validate_body: Whether the body should be validated. Defaults to True.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_db_patch_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "database",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_db_patch_template_fields]
    ui_color = "#ECF4D9"
    operator_extra_links = (CloudSQLInstanceDatabaseLink(),)

    def __init__(
        self,
        *,
        instance: str,
        database: str,
        body: dict,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        validate_body: bool = True,
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.database = database
        self.body = body
        self.validate_body = validate_body
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")
        if not self.database:
            raise AirflowException("The required parameter 'database' is empty")

    def _validate_body_fields(self) -> None:
        if self.validate_body:
            GcpBodyFieldValidator(CLOUD_SQL_DATABASE_PATCH_VALIDATION, api_version=self.api_version).validate(
                self.body
            )

    def execute(self, context: Context) -> None:
        self._validate_body_fields()
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        if not self._check_if_db_exists(self.database, hook):
            raise AirflowException(
                f"Cloud SQL instance with ID {self.instance} does not contain database '{self.database}'. "
                "Please specify another database to patch."
            )
        CloudSQLInstanceDatabaseLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )
        return hook.patch_database(
            project_id=self.project_id, instance=self.instance, database=self.database, body=self.body
        )


class CloudSQLDeleteInstanceDatabaseOperator(CloudSQLBaseOperator):
    """
    Delete a database from a Cloud SQL instance.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLDeleteInstanceDatabaseOperator`

    :param instance: Database instance ID. This does not include the project ID.
    :param database: Name of the database to be deleted in the instance.
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_db_delete_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "database",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_db_delete_template_fields]
    ui_color = "#D5EAD8"

    def __init__(
        self,
        *,
        instance: str,
        database: str,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.database = database
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.database:
            raise AirflowException("The required parameter 'database' is empty")

    def execute(self, context: Context) -> bool | None:
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        if not self._check_if_db_exists(self.database, hook):
            print(
                f"Cloud SQL instance with ID {self.instance!r} does not contain database {self.database!r}. "
                f"Aborting database delete."
            )
            return True
        return hook.delete_database(
            project_id=self.project_id, instance=self.instance, database=self.database
        )


class CloudSQLExportInstanceOperator(CloudSQLBaseOperator):
    """
    Export data from a Cloud SQL instance to a Cloud Storage bucket.

    The exported format can be a SQL dump or CSV file.

    Note: This operator is idempotent. If executed multiple times with the same
    export file URI, the export file in GCS will simply be overridden.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLExportInstanceOperator`

    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param body: The request body, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/export#request-body
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param validate_body: Whether the body should be validated. Defaults to True.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    :param deferrable: Run operator in the deferrable mode.
    :param poke_interval: (Deferrable mode only) Time (seconds) to wait between calls
        to check the run status.
    """

    # [START gcp_sql_export_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_export_template_fields]
    ui_color = "#D4ECEA"
    operator_extra_links = (CloudSQLInstanceLink(), FileDetailsLink())

    def __init__(
        self,
        *,
        instance: str,
        body: dict,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        validate_body: bool = True,
        impersonation_chain: str | Sequence[str] | None = None,
        deferrable: bool = conf.getboolean("operators", "default_deferrable", fallback=False),
        poke_interval: int = 10,
        **kwargs,
    ) -> None:
        self.body = body
        self.validate_body = validate_body
        self.deferrable = deferrable
        self.poke_interval = poke_interval
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")

    def _validate_body_fields(self) -> None:
        if self.validate_body:
            GcpBodyFieldValidator(CLOUD_SQL_EXPORT_VALIDATION, api_version=self.api_version).validate(
                self.body
            )

    def execute(self, context: Context) -> None:
        self._validate_body_fields()
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        CloudSQLInstanceLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )
        FileDetailsLink.persist(
            context=context,
            uri=self.body["exportContext"]["uri"][5:],
            project_id=self.project_id or hook.project_id,
        )

        operation_name = hook.export_instance(
            project_id=self.project_id, instance=self.instance, body=self.body
        )

        if not self.deferrable:
            return hook._wait_for_operation_to_complete(
                project_id=self.project_id, operation_name=operation_name
            )
        self.defer(
            trigger=CloudSQLExportTrigger(
                operation_name=operation_name,
                project_id=self.project_id or hook.project_id,
                gcp_conn_id=self.gcp_conn_id,
                impersonation_chain=self.impersonation_chain,
                poke_interval=self.poke_interval,
            ),
            method_name="execute_complete",
        )

    def execute_complete(self, context, event=None) -> None:
        """
        Act as a callback for when the trigger fires - returns immediately.

        Relies on trigger to throw an exception, otherwise it assumes execution was successful.
        """
        if event["status"] == "success":
            self.log.info("Operation %s completed successfully", event["operation_name"])
        else:
            self.log.exception("Unexpected error in the operation.")
            raise AirflowException(event["message"])


class CloudSQLImportInstanceOperator(CloudSQLBaseOperator):
    """
    Import data into a Cloud SQL instance from Cloud Storage.

    CSV IMPORT
    ``````````

    This operator is NOT idempotent for a CSV import. If the same file is imported
    multiple times, the imported data will be duplicated in the database.
    Moreover, if there are any unique constraints the duplicate import may result in an
    error.

    SQL IMPORT
    ``````````

    This operator is idempotent for a SQL import if it was also exported by Cloud SQL.
    The exported SQL contains 'DROP TABLE IF EXISTS' statements for all tables
    to be imported.

    If the import file was generated in a different way, idempotence is not guaranteed.
    It has to be ensured on the SQL file level.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLImportInstanceOperator`

    :param instance: Cloud SQL instance ID. This does not include the project ID.
    :param body: The request body, as described in
        https://cloud.google.com/sql/docs/mysql/admin-api/v1beta4/instances/import#request-body
    :param project_id: Optional, Google Cloud Project ID. If set to None or missing,
            the default project_id from the Google Cloud connection is used.
    :param gcp_conn_id: The connection ID used to connect to Google Cloud.
    :param api_version: API version used (e.g. v1beta4).
    :param validate_body: Whether the body should be validated. Defaults to True.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    # [START gcp_sql_import_template_fields]
    template_fields: Sequence[str] = (
        "project_id",
        "instance",
        "body",
        "gcp_conn_id",
        "api_version",
        "impersonation_chain",
    )
    # [END gcp_sql_import_template_fields]
    ui_color = "#D3EDFB"
    operator_extra_links = (CloudSQLInstanceLink(), FileDetailsLink())

    def __init__(
        self,
        *,
        instance: str,
        body: dict,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        api_version: str = "v1beta4",
        validate_body: bool = True,
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.body = body
        self.validate_body = validate_body
        super().__init__(
            project_id=project_id,
            instance=instance,
            gcp_conn_id=gcp_conn_id,
            api_version=api_version,
            impersonation_chain=impersonation_chain,
            **kwargs,
        )

    def _validate_inputs(self) -> None:
        super()._validate_inputs()
        if not self.body:
            raise AirflowException("The required parameter 'body' is empty")

    def _validate_body_fields(self) -> None:
        if self.validate_body:
            GcpBodyFieldValidator(CLOUD_SQL_IMPORT_VALIDATION, api_version=self.api_version).validate(
                self.body
            )

    def execute(self, context: Context) -> None:
        self._validate_body_fields()
        hook = CloudSQLHook(
            gcp_conn_id=self.gcp_conn_id,
            api_version=self.api_version,
            impersonation_chain=self.impersonation_chain,
        )
        CloudSQLInstanceLink.persist(
            context=context,
            project_id=self.project_id or hook.project_id,
        )
        FileDetailsLink.persist(
            context=context,
            uri=self.body["importContext"]["uri"][5:],
            project_id=self.project_id or hook.project_id,
        )
        return hook.import_instance(project_id=self.project_id, instance=self.instance, body=self.body)


class CloudSQLExecuteQueryOperator(GoogleCloudBaseOperator):
    """
    Perform DML or DDL query on an existing Cloud Sql instance.

    It optionally uses cloud-sql-proxy to establish secure connection with the
    database.

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:CloudSQLExecuteQueryOperator`

    :param sql: SQL query or list of queries to run (should be DML or DDL query -
        this operator does not return any data from the database,
        so it is useless to pass it DQL queries. Note that it is responsibility of the
        author of the queries to make sure that the queries are idempotent. For example
        you can use CREATE TABLE IF NOT EXISTS to create a table.
    :param parameters: (optional) the parameters to render the SQL query with.
    :param autocommit: if True, each command is automatically committed.
        (default value: False)
    :param gcp_conn_id: The connection ID used to connect to Google Cloud for
        cloud-sql-proxy authentication.
    :param gcp_cloudsql_conn_id: The connection ID used to connect to Google Cloud SQL
       its schema should be gcpcloudsql://.
       See :class:`~airflow.providers.google.cloud.hooks.cloud_sql.CloudSQLDatabaseHook` for
       details on how to define ``gcpcloudsql://`` connection.
    :param sql_proxy_binary_path: (optional) Path to the cloud-sql-proxy binary.
          is not specified or the binary is not present, it is automatically downloaded.
    :param ssl_cert: (optional) Path to client certificate to authenticate when SSL is used. Overrides the
        connection field ``sslcert``.
    :param ssl_key: (optional) Path to client private key to authenticate when SSL is used. Overrides the
        connection field ``sslkey``.
    :param ssl_root_cert: (optional) Path to server's certificate to authenticate when SSL is used. Overrides
        the connection field ``sslrootcert``.
    :param ssl_secret_id: (optional) ID of the secret in Google Cloud Secret Manager that stores SSL
        certificate in the format below:

        {'sslcert': '',
         'sslkey': '',
         'sslrootcert': ''}

        Overrides the connection fields ``sslcert``, ``sslkey``, ``sslrootcert``.
        Note that according to the Secret Manager requirements, the mentioned dict should be saved as a
        string, and encoded with base64.
        Note that this parameter is incompatible with parameters ``ssl_cert``, ``ssl_key``, ``ssl_root_cert``.
    """

    # [START gcp_sql_query_template_fields]
    template_fields: Sequence[str] = (
        "sql",
        "gcp_cloudsql_conn_id",
        "gcp_conn_id",
        "ssl_server_cert",
        "ssl_client_cert",
        "ssl_client_key",
        "ssl_secret_id",
    )
    template_ext: Sequence[str] = (".sql",)
    template_fields_renderers = {"sql": "sql"}
    # [END gcp_sql_query_template_fields]
    ui_color = "#D3DEF1"

    def __init__(
        self,
        *,
        sql: str | Iterable[str],
        autocommit: bool = False,
        parameters: Iterable | Mapping[str, Any] | None = None,
        gcp_conn_id: str = "google_cloud_default",
        gcp_cloudsql_conn_id: str = "google_cloud_sql_default",
        sql_proxy_binary_path: str | None = None,
        ssl_server_cert: str | None = None,
        ssl_client_cert: str | None = None,
        ssl_client_key: str | None = None,
        ssl_secret_id: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.sql = sql
        self.gcp_conn_id = gcp_conn_id
        self.gcp_cloudsql_conn_id = gcp_cloudsql_conn_id
        self.autocommit = autocommit
        self.parameters = parameters
        self.gcp_connection: Connection | None = None
        self.sql_proxy_binary_path = sql_proxy_binary_path
        self.ssl_server_cert = ssl_server_cert
        self.ssl_client_cert = ssl_client_cert
        self.ssl_client_key = ssl_client_key
        self.ssl_secret_id = ssl_secret_id

    @contextmanager
    def cloud_sql_proxy_context(self, hook: CloudSQLDatabaseHook):
        cloud_sql_proxy_runner = None
        try:
            if hook.use_proxy:
                cloud_sql_proxy_runner = hook.get_sqlproxy_runner()
                hook.free_reserved_port()
                # There is very, very slim chance that the socket will
                # be taken over here by another bind(0).
                # It's quite unlikely to happen though!
                cloud_sql_proxy_runner.start_proxy()
            yield
        finally:
            if cloud_sql_proxy_runner:
                cloud_sql_proxy_runner.stop_proxy()

    def execute(self, context: Context):
        hook = self.hook
        hook.validate_ssl_certs()
        connection = hook.create_connection()
        hook.validate_socket_path_length()
        database_hook = hook.get_database_hook(connection=connection)
        try:
            with self.cloud_sql_proxy_context(hook):
                self.log.info('Executing: "%s"', self.sql)
                database_hook.run(self.sql, self.autocommit, parameters=self.parameters)
        finally:
            hook.cleanup_database_hook()

    @cached_property
    def hook(self):
        self.gcp_connection = BaseHook.get_connection(self.gcp_conn_id)
        return CloudSQLDatabaseHook(
            gcp_cloudsql_conn_id=self.gcp_cloudsql_conn_id,
            gcp_conn_id=self.gcp_conn_id,
            default_gcp_project_id=get_field(self.gcp_connection.extra_dejson, "project"),
            sql_proxy_binary_path=self.sql_proxy_binary_path,
            ssl_root_cert=self.ssl_server_cert,
            ssl_cert=self.ssl_client_cert,
            ssl_key=self.ssl_client_key,
            ssl_secret_id=self.ssl_secret_id,
        )

    def get_openlineage_facets_on_complete(self, _) -> OperatorLineage | None:
        from airflow.providers.common.compat.openlineage.utils.sql import get_openlineage_facets_with_sql

        with self.cloud_sql_proxy_context(self.hook):
            return get_openlineage_facets_with_sql(
                hook=self.hook.db_hook,
                sql=self.sql,  # type:ignore[arg-type]  # Iterable[str] instead of list[str]
                conn_id=self.gcp_cloudsql_conn_id,
                database=self.hook.database,
            )
