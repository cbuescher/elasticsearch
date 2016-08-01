This folder contains all necessary scripts to alert when a metric changes significantly (more than 3 std-dev) in a benchmarking trial 
with `night_rally`.

### Prerequisites

Ensure that the Watcher plugin is installed for Rally's Elasticsearch metrics store. 

### Installation

The scripts have to be applied to Rally's Elasticsearch metrics store. They require Watcher and work either on an on-premise Elasticsearch 
installation or on Elastic Cloud. For the nightlies, we use Elastic Cloud.

1. Add scripts:

For an on-premise installation of Elasticsearch put all scripts in the folder `scripts` in `$ES_HOME/config/scripts`. For Elastic 
Cloud, you have to upload the scripts as a [bundle](https://www.elastic.co/guide/en/cloud/current/custom-bundles.html#_layout_of_bundles) 
and activate the bundle.

2. Add the watch

```
curl --user username:password -s -XPUT https://your-elastic-cloud-instance:9243/_watcher/watch/nightlyAlert --data-binary @watch.json
```

