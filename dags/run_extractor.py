import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator

with DAG(
    dag_id="run_ext_and_dbt_build",
    start_date=pendulum.datetime(2026, 11, 1, tz="Europe/Prague"),
    schedule="0 7 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0},
) as dag:

    extractor = BashOperator(
                task_id="run_extractor",
                bash_command="uv run dags/python/extractor.py",
                cwd="/home/pi/ATS_elt",
                retries=2,
                retry_delay=pendulum.duration(minutes=10),
                execution_timeout=pendulum.duration(minutes=30),
                )

    gcp_upload = BashOperator(
                task_id="gcp_upload",
                bash_command="uv run dags/python/upload.py",
                cwd="/home/pi/ATS_elt",
                env={"GOOGLE_APPLICATION_CREDENTIALS": "/home/pi/.config/ats/sa-key.json"},
                append_env=True,
                retries=2,
                retry_delay=pendulum.duration(minutes=10),
                execution_timeout=pendulum.duration(minutes=30),
                )
    
    dbt_build = BashOperator(
                task_id="dbt_build", 
                bash_command="uv run dbt build", 
                cwd="/home/pi/ATS_elt/dbt/",
                execution_timeout=pendulum.duration(minutes=30),
                )

    extractor >> [gcp_upload, dbt_build]
