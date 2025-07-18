 .. Licensed to the Apache Software Foundation (ASF) under one
    or more contributor license agreements.  See the NOTICE file
    distributed with this work for additional information
    regarding copyright ownership.  The ASF licenses this file
    to you under the Apache License, Version 2.0 (the
    "License"); you may not use this file except in compliance
    with the License.  You may obtain a copy of the License at

 ..   http://www.apache.org/licenses/LICENSE-2.0

 .. Unless required by applicable law or agreed to in writing,
    software distributed under the License is distributed on an
    "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
    KIND, either express or implied.  See the License for the
    specific language governing permissions and limitations
    under the License.

Google Display & Video 360 Operators
=======================================
`Google Display & Video 360 <https://marketingplatform.google.com/about/display-video-360/>`__ has the end-to-end
campaign management features you need.

Prerequisite Tasks
^^^^^^^^^^^^^^^^^^

.. include:: /operators/_partials/prerequisite_tasks.rst

.. _howto/operator:GoogleDisplayVideo360CreateReportOperator:

Creating a Query
^^^^^^^^^^^^^^^^

.. warning::
    This operator is deprecated and will be removed after September 01, 2025. Please use
    :class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateSDFDownloadTaskOperator`.

To create Display&Video 360 query use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateQueryOperator`.

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateQueryOperator`
parameters which allow you to dynamically determine values. You can provide body definition using ``
.json`` file as this operator supports this template extension.
The result is saved to :ref:`XCom <concepts:xcom>`, which allows the result to be used by other operators.

.. _howto/operator:GoogleDisplayVideo360RunQueryOperator:

Run Query
^^^^^^^^^

.. warning::
    This operator is deprecated and will be removed after September 01, 2025. Please use
    :class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateSDFDownloadTaskOperator`.

:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360RunQueryOperator`.

You can use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360RunQueryOperator`
parameters which allow you to dynamically determine values.
The result is saved to :ref:`XCom <concepts:xcom>`, which allows the result to be used by other operators.

.. _howto/operator:GoogleDisplayVideo360DeleteReportOperator:

Deleting a report
^^^^^^^^^^^^^^^^^

.. warning::
    This operator is deprecated and will be removed after September 01, 2025.
    Display & Video 360 API v2 has been deprecated and will be removed. Reports were replaced with SDF
    export task in v4 of API.

To delete Display&Video 360 report use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DeleteReportOperator`.

You can use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DeleteReportOperator`
parameters which allow you to dynamically determine values.

.. _howto/operator:GoogleDisplayVideo360RunQuerySensor:

Waiting for query
^^^^^^^^^^^^^^^^^

.. warning::
    This sensor is deprecated and will be removed after September 01, 2025.
    Display & Video 360 API v2 has been deprecated and will be removed. Queries were replaced with SDF
    export task in v4 of API.

To wait for the report use
:class:`~airflow.providers.google.marketing_platform.sensors.display_video.GoogleDisplayVideo360RunQuerySensor`.

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.sensors.display_video.GoogleDisplayVideo360RunQuerySensor`
parameters which allow you to dynamically determine values.

.. _howto/operator:GoogleDisplayVideo360DownloadReportV2Operator:

Downloading a report
^^^^^^^^^^^^^^^^^^^^

.. warning::
    This operator is deprecated and will be removed after September 01, 2025. Please use
    :class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360SDFtoGCSOperator`.

To download a report to GCS bucket use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DownloadReportV2Operator`.

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DownloadReportV2Operator`
parameters which allow you to dynamically determine values.

.. _howto/operator:GoogleDisplayVideo360DownloadLineItemsOperator:

Downloading Line Items
^^^^^^^^^^^^^^^^^^^^^^

The operator accepts body request:

- consistent with `Google API <https://developers.google.com/bid-manager/v1.1/lineitems/downloadlineitems>`_ ::

    REQUEST_BODY = {
    "filterType": ADVERTISER_ID,
    "format": "CSV",
    "fileSpec": "EWF"
    }

.. warning::
    This operator is deprecated and will be removed after September 01, 2025. Please use
    :class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateSDFDownloadTaskOperator`.

To download line items in CSV format report use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DownloadLineItemsOperator`.

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360DownloadLineItemsOperator`
parameters which allow you to dynamically determine values.


.. _howto/operator:GoogleDisplayVideo360UploadLineItemsOperator:

Upload line items
^^^^^^^^^^^^^^^^^

.. warning::
    This operator is deprecated and will be removed after September 01, 2025. Please use
    :class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360SDFtoGCSOperator`.

To run Display&Video 360 uploading line items use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360UploadLineItemsOperator`.

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360UploadLineItemsOperator`
parameters which allow you to dynamically determine values.

.. _howto/operator:GoogleDisplayVideo360CreateSDFDownloadTaskOperator:

Create SDF download task
^^^^^^^^^^^^^^^^^^^^^^^^

To create SDF download task use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateSDFDownloadTaskOperator`.

.. exampleinclude:: /../../google/tests/system/google/marketing_platform/example_display_video.py
    :language: python
    :dedent: 4
    :start-after: [START howto_google_display_video_create_sdf_download_task_operator]
    :end-before: [END howto_google_display_video_create_sdf_download_task_operator]

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360CreateSDFDownloadTaskOperator`
parameters which allow you to dynamically determine values.


.. _howto/operator:GoogleDisplayVideo360SDFtoGCSOperator:

Save SDF files in the Google Cloud Storage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To save SDF files and save them in the Google Cloud Storage use
:class:`~airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360SDFtoGCSOperator`.

.. exampleinclude:: /../../google/tests/system/google/marketing_platform/example_display_video.py
    :language: python
    :dedent: 4
    :start-after: [START howto_google_display_video_save_sdf_in_gcs_operator]
    :end-before: [END howto_google_display_video_save_sdf_in_gcs_operator]

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.operators.display_video.GoogleDisplayVideo360SDFtoGCSOperator`
parameters which allow you to dynamically determine values.

.. _howto/operator:GoogleDisplayVideo360GetSDFDownloadOperationSensor:

Waiting for SDF operation
^^^^^^^^^^^^^^^^^^^^^^^^^

Wait for SDF operation is executed by:
:class:`~airflow.providers.google.marketing_platform.sensors.display_video.GoogleDisplayVideo360GetSDFDownloadOperationSensor`.

.. exampleinclude:: /../../google/tests/system/google/marketing_platform/example_display_video.py
    :language: python
    :dedent: 4
    :start-after: [START howto_google_display_video_wait_for_operation_sensor]
    :end-before: [END howto_google_display_video_wait_for_operation_sensor]

Use :ref:`Jinja templating <concepts:jinja-templating>` with
:template-fields:`airflow.providers.google.marketing_platform.sensors.display_video.GoogleDisplayVideo360GetSDFDownloadOperationSensor`
parameters which allow you to dynamically determine values.
