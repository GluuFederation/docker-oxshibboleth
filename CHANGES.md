# Changelog

Here you can see an overview of changes between each release.

## Version 4.1.0_01

Released on March 5th, 2020.

* Conformed to Gluu Server v4.1.

## Version 4.0.1_05

Released on March 5th, 2020.

* Upgraded `oxshibbolethIdp`.
* Added ENV for customizing Couchbase connection and scan consistency.

## Version 4.0.1_04

Released on January 3rd, 2020.

* Fixed invalid tag in `idp-metadata.xml` template.

## Version 4.0.1_03

Released on December 1st, 2019.

* Upgraded `oxshibbolethIdp` v4.0.1.Final build at 2019-11-30.

## Version 4.0.1_02

Released on November 14th, 2019.

* Upgraded `pygluu-containerlib` to show connection issue with Couchbase explicitly.

## Version 4.0.1_01

Released on November 1st, 2019.

* Upgraded to Gluu Server 4.0.1.

## Version 4.0.0_01

Released on October 22nd, 2019.

* Upgraded to Gluu Server 4.0.

## Version 3.1.6_02

Released on May 10th, 2019.

* Alpine upgraded to v3.9. Ref: https://github.com/GluuFederation/gluu-docker/issues/71.

## Version 3.1.6_01

Released on April 29th, 2019.

* Upgraded to Gluu Server 3.1.6.

## Version 3.1.5_03

Released on May 10th, 2019.

* Alpine upgraded to v3.9. Ref: https://github.com/GluuFederation/gluu-docker/issues/71.

## Version 3.1.5_02

Released on April 9th, 2019.

* Added license info on container startup.
* Disabled `sendServerVersion` config of Jetty server.

## Version 3.1.5_01

Released on March 23rd, 2019.

* Upgraded to Gluu Server 3.1.5.

## Version 3.1.4_02

Released on April 4th, 2019.

* Added license info during container run.

## Version 3.1.4_01

Released on November 12th, 2018.

* Upgraded to Gluu Server 3.1.4.

## Version 3.1.3_06

Released on September 18th, 2018.

* Changed base image to use Alpine 3.8.1.

## Version 3.1.3_05

Released on September 12th, 2018.

* Added feature to connect to secure Consul (HTTPS).

## Version 3.1.3_04

Released on August 31st, 2018.

* Added Tini to handle signal forwarding and reaping zombie processes.

## Version 3.1.3_03

Released on July 31st, 2018.

* Fixed template for LDAP password.
* Fixed missing files pulled from shared Shibboleth directory.

## Version 3.1.3_02

Released on July 20th, 2018.

* Added wrapper to manage config via Consul KV or Kubernetes configmap.

## Version 3.1.3_01

Released on June 6th, 2018.

* Upgraded to Gluu Server 3.1.3.

## Version 3.1.2_01

Released on June 6th, 2018.

* Upgraded to Gluu Server 3.1.2.
