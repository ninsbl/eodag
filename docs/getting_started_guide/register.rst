.. _register:

Provider registration
=====================

The providers usually require their user to register to their service. As a result,
the users obtain a set of credentials (e.g. login/password, API key, etc.). These credentials
need to be provided to ``eodag`` (see :ref:`configure`). The list below explains how to register
to each provider supported by ``eodag``:

* ``usgs``: create an account  `here <https://ers.cr.usgs.gov/register/>`__ and then `request an access <https://ers.cr.usgs.gov/profile/access>`_ to the `Machine-to-Machine (M2M) API <https://m2m.cr.usgs.gov/>`_.
  Product requests can be performed once access to the M2M API has been granted to you.

* ``theia``: create an account `here <https://sso.theia-land.fr/theia/register/register.xhtml>`__

* ``peps``: create an account `here <https://peps.cnes.fr/rocket/#/register>`__, then use your email as `username` in eodag credentials.

* ``creodias``: create an account `here <https://portal.creodias.eu/register.php>`__, then use your `username`, `password` in eodag credentials. You will also
  need `totp` in credentials, a temporary 6-digits OTP (One Time Password, see
  `Creodias documentation <https://creodias.docs.cloudferro.com/en/latest/gettingstarted/Two-Factor-Authentication-for-Creodias-Site.html>`__)
  to be able to authenticate and download. Check
  `Authenticate using an OTP <https://eodag.readthedocs.io/en/latest/getting_started_guide/configure.html#authenticate-using-an-otp-one-time-password-two-factor-authentication>`__
  to see how to proceed.

* ``creodias_s3``: Create an account on `creodias <https://creodias.eu/>`__, then go to `keymanager <https://eodata-keymanager.creodias.eu/>`__ and
  click `Add credential` to generate the s3 access key and secret key. Add those credentials to the user configuration file (variables `aws_access_key_id` and `aws_secret_access_key`).

* ``onda``: create an account `here: <https://www.onda-dias.eu/cms/>`__

* ``ecmwf``: create an account `here <https://apps.ecmwf.int/registration/>`__.
  Then use *email* as *username* and *key* as *password* from `here <https://api.ecmwf.int/v1/key/>`__ in eodag credentials.
  EODAG can be used to request for public datasets as for operational archive. Please note that for public datasets you
  might need to accept a license (e.g. for `TIGGE <https://apps.ecmwf.int/datasets/data/tigge/licence/>`__)

* ``cop_ads``: create an account `here <https://ads.atmosphere.copernicus.eu/user/register>`__.
  Then go to your profile and use from the section named "API key" the *UID* as *username* and *API Key* as *password* in eodag credentials.
  EODAG can be used to request for public datasets, you can browse them `here <https://ads.atmosphere.copernicus.eu/cdsapp#!/search?type=dataset>`__.

* ``cop_cds``: create an account `here <https://cds.climate.copernicus.eu/user/register>`__.
  Then go to your profile and use from the section named "API key" use *UID* as *username* and *API Key* as *password* in eodag credentials.
  EODAG can be used to request for public datasets, you can browse them `here <https://cds.climate.copernicus.eu/cdsapp#!/search?type=dataset>`__.

* ``cop_marine``: no account is required

* ``sara``: create an account `here <https://copernicus.nci.org.au/sara.client/#/register>`__, then use your email as `username` in eodag credentials.

* ``meteoblue``: eodag uses `dataset API <https://content.meteoblue.com/en/business-solutions/weather-apis/dataset-api>`_
  which requires the access level `Access Gold <https://content.meteoblue.com/en/business-solutions/weather-apis/pricing>`_.
  Contact `support@meteoblue.com <mailto:support@meteoblue.com>`_ to apply for a free API key trial.

* ``cop_dataspace``: create an account `here <https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/auth?client_id=cdse-public&redirect_uri=https%3A%2F%2Fdataspace.copernicus.eu%2Fbrowser%2F&response_type=code&scope=openid>`__

* ``planetary_computer``: most datasets are anonymously accessible, but a subscription key may be needed to increase `rate limits and access private datasets <https://planetarycomputer.microsoft.com/docs/concepts/sas/#rate-limits-and-access-restrictions>`_.
  Create an account `here <https://planetarycomputer.microsoft.com/account/request>`__, then view your keys by signing in with your Microsoft account `here <https://planetarycomputer.developer.azure-api.net/>`__.

* ``hydroweb_next``: Go to `https://hydroweb.next.theia-land.fr <https://hydroweb.next.theia-land.fr>`_, then login or
  create an account by clicking on ``Log in`` in the top-right corner. Once logged-in, create an API key in the user
  settings page, and used it as *apikey* in EODAG provider auth credentials.

* ``aws_eos``: you need credentials for both EOS (search) and AWS (download):

  * Create an account on `EOS <https://auth.eos.com>`__

  * Get your EOS api key from `here <https://api-connect.eos.com/user-dashboard/statistics>`__

  * Create an account on `AWS <https://aws.amazon.com/>`__

  * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__

  * Click on user, then on your user name and then on security credentials.

  * In access keys, click on create access key.

  * Add these credentials to the user configuration file.

.. note::

    EOS free account is limited to 100 requests.

* ``astraea_eod``, ``earth_search``, ``usgs_satapi_aws``: you need AWS credentials for download:

  * Create an account on `AWS <https://aws.amazon.com/>`__

  * Once the account is activated go to the `identity access management console <https://console.aws.amazon.com/iam/home#/home>`__

  * Click on user, then on your user name and then on security credentials.

  * In access keys, click on create access key.

  * Add these credentials to the user configuration file.

.. warning::

    A credit card number must be provided when creating an AWS account because fees apply
    after a given amount of downloaded data.

* ``earth_search_gcs``: you need HMAC keys for Google Cloud Storage:

  * Sign in using a `google account <https://accounts.google.com/signin/v2/identifier>`__.

  * Get or create `HMAC keys <https://cloud.google.com/storage/docs/authentication/hmackeys>`__ for your user account
    on a project for interoperability API access from this
    `page <https://console.cloud.google.com/storage/settings;tab=interoperability>`__ (create a default project if
    none exists).

  * Add these credentials to the user configuration file.

* ``earth_search_cog``: no authentication needed.

* ``wekeo``: you need an access token to authenticate and to accept terms and conditions with it:

  * Create an account on `WEkEO <https://www.wekeo.eu/register>`__

  * Add your WEkEO credentials (*username*, *password*) to the user configuration file.

  * Depending on which data you want to retrieve, you will then need to accept terms and conditions (for once). To do this, follow the
    `tutorial guidelines <https://eodag.readthedocs.io/en/latest/notebooks/tutos/tuto_wekeo.html#Registration>`__
    or run the following commands in your terminal.

  * First, get a token from your base64-encoded credentials (replace USERNAME and PASSWORD with your credentials):

    .. code-block:: bash

      curl -X POST --data '{"username": "USERNAME", "password": "PASSWORD"}' -H "Content-Type: application/json" "https://gateway.prod.wekeo2.eu/hda-broker/gettoken"

    The WEkEO API will respond with a token:

    .. code-block:: bash

      { "access_token": "xxxxxxxx-yyyy-zzzz-xxxx-yyyyyyyyyyyy",
        "refresh_token": "xxxxxxxx-yyyy-zzzz-xxxx-yyyyyyyyyyyy",
        "scope":"openid",
        "id_token":"token",
        "token_type":"Bearer",
        "expires_in":3600
      }

  * Accept terms and conditions by running this command and replacing <access_token> and <licence_name>:

    .. code-block:: bash

      curl --request PUT --header 'accept: application/json' --header 'Authorization: Bearer <access_token>' https://gateway.prod.wekeo2.eu/hda-broker/api/v1/termsaccepted/<licence_name>

    The licence name depends on which data you want to retrieve. To use all datasets available in wekeo, the following licences have to be accepted:

    * EUMETSAT_Copernicus_Data_Licence
    * Copernicus_Land_Monitoring_Service_Data_Policy
    * Copernicus_Sentinel_License
    * Copernicus_ECMWF_License
    * Copernicus_DEM_Instance_COP-DEM-GLO-30-F_Global_30m
    * Copernicus_DEM_Instance_COP-DEM-GLO-90-F_Global_90m

* ``wekeo_cmems``: The registration procedure is the same as for ``wekeo``. The licence that has to be accepted to access the Copernicus Marine data is ``Copernicus_Marine_Service_Product_License``.

* ``dedt_lumi``: Create an account on `DestinE <https://platform.destine.eu/>`__, then use your `username`, `password` in eodag credentials.

* ``dedl``: You need a `DESP OpenID` account in order to authenticate. To create one go
  `here <https://hda.data.destination-earth.eu/ui>`__, then click on `Sign In`, select the identity provider
  `DESP OpenID` and then click `Authenticate`. Finally click on `Register` to create a new account.

* ``eumetsat_ds``: create an account `here <https://eoportal.eumetsat.int/userMgmt/register.faces>`__.
  Then use the consumer key as `username` and the consumer secret as `password` from `here <https://api.eumetsat.int/api-key/>`__ in eodag credentials.
