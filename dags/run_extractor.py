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

    first = BashOperator(
    task_id="run_extractor",
    bash_command="uv run dags/python/extractor.py",
    cwd="/home/pi/ATS_elt",
	)
    second = BashOperator(task_id="dbt_build", bash_command="uv run dbt build", cwd="/home/pi/ATS_elt/dbt/")

    first >> second
