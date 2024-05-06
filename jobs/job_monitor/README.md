# OCI Job Monitor UI tool

Incubator project to augment the OCI console with useful functionality to support development of Data Science Jobs.

This job monitor is a Python Flask app build on top of [Oracle ADS](https://docs.oracle.com/en-us/iaas/tools/ads-sdk/latest/index.html).
It allows users to monitor the status and outputs of OCI data science job runs.

![Job Monitor UI](assets/images/job_monitor.png)

Features:

* See the status of recent job runs in your project in a single page.
* See logs of each job run with auto-refresh.
  * Logs are rendered with ANSI color code.
  * Support showing 1000+ log messages at the same time.
  * Logs will be displayed separately even if multiple job runs using same log ID.
  * See YAML representation of the job.
* Download the logs of a job run in a text file.
* Delete job and the corresponding runs.
* Run a new job, including distributed training job, with YAML.

## How to run

### Requirements

This tool requires `oci>=2.45.1` and `oracle-ads>=2.9.0`.

```bash
pip install oci oracle-ads flask --upgrade
```

### Command Line

This tool uses OCI API key or security token for authentication. Make sure your OCI config file (located at `~/.oci/config` by default) has at least one profile before starting the app. The `DEFAULT` profile will be used. If you would like to use a different profile, you can specify it with the `OCI_KEY_PROFILE` environment variable or select it from the UI dropdown once the app is started.
To start the Flask app, simply run the following command and open <http://127.0.0.1:5000/> with your browser.

```bash
FLASK_APP=job_monitor flask run
```

To change the profile and the location of the OCI KEY use following environment variables in the command line:
* `OCI_KEY_PROFILE="DEFAULT"`
* `OCI_KEY_LOCATION="~/.oci/config"`


```bash
FLASK_APP=job_monitor OCI_KEY_PROFILE=PROFILE_NAME flask run
```

The dropdown options for selecting compartment and project only show the ones in the default tenancy. If you need to override the tenancy, you can specify the in environment variable.

```bash
FLASK_APP=job_monitor OCI_KEY_PROFILE=PROFILE_NAME TENANCY_OCID=ocid1.xxx flask run
```

Alternatively, you can specify the compartment OCID and project OCID in the URL:

```bash
http://127.0.0.1:5000/<COMPARTMENT_OCID>/<PROJECT_OCID>
```

### Extra configurations

You may add extra key value pairs to `~/.oci/config.json` as configurations for a profile. These configurations will be used as the context (for the YAML template) when starting a job from YAML. Here is an example of the `~/.oci/config.json`, where `DEV` is the profile name matching the one in `~/.oci/config`:

```
{
    "DEV": {
        "name": "dev - prod - Ashburn",
        "override_tenancy": "ocid1.tenancy.oc1..xxx",
        "compartment_id": "ocid1.compartment.oc1..xxx",
        "log_group_id": "ocid1.loggroup.oc1.iad.xxx",
        "log_id": "ocid1.log.oc1.iad.xxx",
        "project_id": "ocid1.datascienceproject.oc1.iad.xxx",
        "subnet_id": "ocid1.subnet.oc1.iad.xxx",
        "namespace": "oci"
    }
}
```

### VS Code Launch Config

The following config can be used in the VS Code `launch.json` to launch the Flask app. You may need to change the value of `FLASK_APP` to your local path if your default directory is not the root of this project.

```json
{
    "name": "Jobs Monitor",
    "type": "python",
    "request": "launch",
    "module": "flask",
    "env": {
        "FLASK_APP": "job_monitor.py",
        "FLASK_ENV": "development",
        // OCI_KEY_PROFILE="DEFAULT",
        // OCI_KEY_PROFILE="~/.oci/config"
    },
    "args": [
        "run",
        "--no-debugger"
    ],
    "jinja": true
},
```
