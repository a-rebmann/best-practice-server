# Best-Practice Checker

This repository contains the code of the server of the Best-Practice Checker. 
This README provides instructions to setup the back end as well as the reuqired data base

For the front end code see [here](https://github.com/a-rebmann/best-practice-client-)


## Setup Database
We use a MongoDB database in the cloud.
Follow [this](https://www.mongodb.com/lp/cloud/atlas/try4?utm_source=google&utm_campaign=search_gs_pl_evergreen_atlas_general_prosp-brand_gic-null_emea-de_ps-all_desktop_eng_lead&utm_term=mongo%20db%20tutorial&utm_medium=cpc_paid_search&utm_ad=p&utm_ad_campaign_id=1718986504&adgroup=80209773523&cq_cmp=1718986504&gad_source=1&gclid=CjwKCAjwoJa2BhBPEiwA0l0ImBnvBOpK75OlXLZ_jS8SyWF8RPRV3P51XbR42xK1r1IHvmwTXRTY8xoCJa0QAvD_BwE) tutorial if you want to do the same.

You can anturally also setup a local database, e.g., as a Docker container (see [here](https://www.mongodb.com/docs/manual/tutorial/install-mongodb-community-with-docker/)).

Regardless to the installation you need to create an database called "bestPracticeData".

## Setup Backend

1. Create a Python virtual environment (we used Python 3.12)
2. Install the dependencies in requirements.txt
3. Create a <code>.env</code> file in the root of the project with the following environment variables:

<code>
    HOST=0.0.0.0
    PORT=8000
    ROOT_PATH=/api
    DB_USER=[RELACE WITH YOUR DB USER]
    DB_PASSWORD=[RELACE WITH YOUR DB PASSWORD]
    DB_URI=[RELACE WITH YOUR DB URI]
    SSL_KEY_PATH=path/to/ssl-key (optional)
    SSL_CERT_PATH=path/to/ssl-cert (optional)
    DEVELOPMENT=true/false

    SIGNAVIO_USER=[RELACE WITH YOUR SIGNAVIO ACADEMIC USER] (optional, needed for process model viewer)
    SIGNAVIO_PASSWORD=[RELACE WITH YOUR SIGNAVIO ACADEMIC PASSWORD] (optional, needed for process model viewer)
    SIGNAVIO_URL=https://academic.signavio.com
    SIGNAVIO_WORKSPACE=[RELACE WITH YOUR SIGNAVIO ACADEMIC WORKSPACE] (optional, needed for process model viewer)
</code>

4. Run <code>python main.py</code> from the root.

