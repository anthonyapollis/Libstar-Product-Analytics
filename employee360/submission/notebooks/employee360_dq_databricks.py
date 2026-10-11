# Databricks notebook source
# COMMAND ----------
# Run in a Databricks Python notebook or job.
# Parameters may be passed as widgets: input_dir and output_dir.
from pyspark.sql import functions as F
from pyspark.sql.window import Window

try:
    input_dir = dbutils.widgets.get('input_dir')
except Exception:
    input_dir = '/FileStore/employee360/input'
try:
    output_dir = dbutils.widgets.get('output_dir')
except Exception:
    output_dir = '/FileStore/employee360/output'

def csv(name):
    return spark.read.option('header', True).option('inferSchema', False).csv(f'{input_dir}/{name}')

def issue(rule, employee_col, source, detail, severity, action):
    return (employee_col.select(F.lit(rule).alias('rule_id'), F.col('employee_id'),
                               F.lit(source).alias('source'), F.lit(detail).alias('detail'),
                               F.lit(severity).alias('severity'), F.lit(action).alias('release_action')))

hr = csv('HR_Source.csv')
payroll = csv('Payroll_Source.csv')
e360 = csv('Employee_360.csv')

# DQ01: duplicates in every source.
dq01 = None
for name, df in [('HR', hr), ('Payroll', payroll), ('Employee_360', e360)]:
    x = df.groupBy('employee_id').count().where('count > 1').select('employee_id')
    part = issue('DQ01', x, name, 'duplicate employee_id', 'Critical', 'Block release')
    dq01 = part if dq01 is None else dq01.unionByName(part)

# DQ02 mandatory HR fields; DQ03 manager referential integrity.
dq02 = None
for column in ['email', 'department', 'full_name', 'employment_status']:
    x = hr.where(F.trim(F.coalesce(F.col(column), F.lit(''))) == '').select('employee_id')
    part = issue('DQ02', x, 'HR', f'blank: {column}', 'Medium', 'Monitor')
    dq02 = part if dq02 is None else dq02.unionByName(part)
manager_ids = hr.select(F.col('employee_id').alias('known_manager_id')).distinct()
dq03 = issue('DQ03', hr.where(F.col('manager_id').isNotNull() & (F.trim('manager_id') != ''))
                   .join(manager_ids, hr.manager_id == manager_ids.known_manager_id, 'left_anti').select('employee_id'),
             'HR', 'manager_id is not in HR', 'High', 'Alert now')

# DQ04 expected payroll status, DQ05 valid currency/value, DQ06 freshness.
pay_status = payroll.groupBy('employee_id').agg(F.collect_set('payroll_status').alias('statuses'))
dq04 = issue('DQ04', hr.join(pay_status, 'employee_id', 'left')
                 .where((F.col('employment_status') == 'Active') & (~F.array_contains(F.coalesce(F.col('statuses'), F.array()), 'Payable')))
                 .select('employee_id'), 'HR vs Payroll', 'Active HR employee is not Payable in payroll', 'Critical', 'Alert now')
dq05 = issue('DQ05', payroll.where((F.col('currency') != 'ZAR') | (F.col('monthly_salary_zar').cast('double') <= 0) | F.col('monthly_salary_zar').cast('double').isNull()).select('employee_id'),
             'Payroll', 'salary must be positive and currency ZAR', 'High', 'Block release')
cutoff = F.to_date(F.lit('2026-07-10'))
dq06 = None
for name, df in [('HR',hr),('Payroll',payroll),('Employee_360',e360)]:
    x = df.where(F.to_date('last_updated') < cutoff).select('employee_id')
    part = issue('DQ06', x, name, 'last_updated is older than freshness threshold', 'Medium', 'Monitor')
    dq06 = part if dq06 is None else dq06.unionByName(part)

# DQ07 detects conflicts rather than taking an arbitrary first payroll value.
pay_conflicts = payroll.groupBy('employee_id','pay_period').agg(F.countDistinct(F.struct('monthly_salary_zar','currency')).alias('distinct_values')).where('distinct_values > 1').select('employee_id').distinct()
dq07 = issue('DQ07', pay_conflicts, 'Payroll', 'conflicting salary/currency values: cannot verify', 'Critical', 'Block release')

# RC01/RC02 and RC03 field-level reconciliation.
dq_rc01 = issue('RC01', hr.select('employee_id').join(e360.select('employee_id'),'employee_id','left_anti'), 'HR vs Employee_360', 'Missing downstream', 'Critical', 'Block release')
dq_rc02 = issue('RC02', e360.select('employee_id').join(hr.select('employee_id'),'employee_id','left_anti'), 'HR vs Employee_360', 'Unexpected downstream', 'Critical', 'Block release')
pay_one = payroll.join(pay_conflicts,'employee_id','left_anti').select('employee_id','monthly_salary_zar','currency').distinct().withColumn('_pay_present', F.lit(True))
rc03_cannot_verify = issue('RC03', pay_conflicts, 'Payroll vs Employee_360', 'Cannot verify: conflicting payroll values', 'Critical', 'Block release')
joined = hr.alias('h').join(e360.alias('e'),'employee_id','inner').join(pay_one.alias('p'),'employee_id','left')
rc03_field = issue('RC03', joined.where((F.col('h.employment_status') != F.col('e.employment_status')) | F.col('p._pay_present').isNull() | (F.col('p.monthly_salary_zar') != F.col('e.monthly_salary_zar')) | (F.col('p.currency') != F.col('e.currency'))).select('employee_id'),
                     'Source vs Employee_360', 'status, salary or currency mismatch', 'Critical', 'Block release')

issues = dq01.unionByName(dq02).unionByName(dq03).unionByName(dq04).unionByName(dq05).unionByName(dq06).unionByName(dq07).unionByName(dq_rc01).unionByName(dq_rc02).unionByName(rc03_cannot_verify).unionByName(rc03_field)
issues.write.mode('overwrite').format('delta').saveAsTable('employee360_dq_issue_detail')

rules = spark.createDataFrame([
 ('DQ01','Uniqueness','Critical','Block release'),('DQ02','Completeness','Medium','Monitor'),('DQ03','Referential integrity','High','Alert now'),('DQ04','Consistency','Critical','Alert now'),('DQ05','Validity','High','Block release'),('DQ06','Timeliness','Medium','Monitor'),('DQ07','Consistency','Critical','Block release'),('RC01','Reconciliation','Critical','Block release'),('RC02','Reconciliation','Critical','Block release'),('RC03','Reconciliation','Critical','Block release')], ['rule_id','dimension','severity','release_action'])
monitoring = rules.join(issues.groupBy('rule_id').count().withColumnRenamed('count','affected_count'),'rule_id','left').fillna({'affected_count':0}).withColumn('status',F.when(F.col('affected_count')>0,'FAIL').otherwise('PASS'))
monitoring.write.mode('overwrite').format('delta').saveAsTable('employee360_dq_monitoring')

# A failed rule is a data-quality result. The notebook/job itself can still succeed.
display(monitoring.orderBy('rule_id'))
# COMMAND ----------

