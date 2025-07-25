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
"""This module contains Google Cloud Bigtable sensor."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import google.api_core.exceptions
from google.cloud.bigtable import enums
from google.cloud.bigtable.table import ClusterState

from airflow.providers.google.cloud.hooks.bigtable import BigtableHook
from airflow.providers.google.cloud.links.bigtable import BigtableTablesLink
from airflow.providers.google.cloud.operators.bigtable import BigtableValidationMixin
from airflow.providers.google.common.hooks.base_google import PROVIDE_PROJECT_ID
from airflow.providers.google.version_compat import AIRFLOW_V_3_0_PLUS

if AIRFLOW_V_3_0_PLUS:
    from airflow.sdk import BaseSensorOperator
else:
    from airflow.sensors.base import BaseSensorOperator  # type: ignore[no-redef]

if TYPE_CHECKING:
    from airflow.utils.context import Context


class BigtableTableReplicationCompletedSensor(BaseSensorOperator, BigtableValidationMixin):
    """
    Sensor that waits for Cloud Bigtable table to be fully replicated to its clusters.

    No exception will be raised if the instance or the table does not exist.

    For more details about cluster states for a table, have a look at the reference:
    https://googleapis.github.io/google-cloud-python/latest/bigtable/table.html#google.cloud.bigtable.table.Table.get_cluster_states

    .. seealso::
        For more information on how to use this operator, take a look at the guide:
        :ref:`howto/operator:BigtableTableReplicationCompletedSensor`

    :param instance_id: The ID of the Cloud Bigtable instance.
    :param table_id: The ID of the table to check replication status.
    :param project_id: Optional, the ID of the Google Cloud project.
    :param impersonation_chain: Optional service account to impersonate using short-term
        credentials, or chained list of accounts required to get the access_token
        of the last account in the list, which will be impersonated in the request.
        If set as a string, the account must grant the originating account
        the Service Account Token Creator IAM role.
        If set as a sequence, the identities from the list must grant
        Service Account Token Creator IAM role to the directly preceding identity, with first
        account from the list granting this role to the originating account (templated).
    """

    REQUIRED_ATTRIBUTES = ("instance_id", "table_id")
    template_fields: Sequence[str] = (
        "project_id",
        "instance_id",
        "table_id",
        "impersonation_chain",
    )
    operator_extra_links = (BigtableTablesLink(),)

    def __init__(
        self,
        *,
        instance_id: str,
        table_id: str,
        project_id: str = PROVIDE_PROJECT_ID,
        gcp_conn_id: str = "google_cloud_default",
        impersonation_chain: str | Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        self.project_id = project_id
        self.instance_id = instance_id
        self.table_id = table_id
        self.gcp_conn_id = gcp_conn_id
        self._validate_inputs()
        self.impersonation_chain = impersonation_chain
        super().__init__(**kwargs)

    @property
    def extra_links_params(self) -> dict[str, Any]:
        return {
            "instance_id": self.instance_id,
            "project_id": self.project_id,
        }

    def poke(self, context: Context) -> bool:
        hook = BigtableHook(
            gcp_conn_id=self.gcp_conn_id,
            impersonation_chain=self.impersonation_chain,
        )
        instance = hook.get_instance(project_id=self.project_id, instance_id=self.instance_id)
        if not instance:
            self.log.info("Dependency: instance '%s' does not exist.", self.instance_id)
            return False

        try:
            cluster_states = hook.get_cluster_states_for_table(instance=instance, table_id=self.table_id)
        except google.api_core.exceptions.NotFound:
            self.log.info(
                "Dependency: table '%s' does not exist in instance '%s'.", self.table_id, self.instance_id
            )
            return False

        ready_state = ClusterState(enums.Table.ReplicationState.READY)

        is_table_replicated = True
        for cluster_id in cluster_states.keys():
            if cluster_states[cluster_id] != ready_state:
                self.log.info("Table '%s' is not yet replicated on cluster '%s'.", self.table_id, cluster_id)
                is_table_replicated = False

        if not is_table_replicated:
            return False

        self.log.info("Table '%s' is replicated.", self.table_id)
        BigtableTablesLink.persist(context=context)
        return True
