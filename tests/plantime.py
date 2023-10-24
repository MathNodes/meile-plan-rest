from datetime import datetime, date
from dateutil.relativedelta import relativedelta


MONTHS = 5
now = date.today()
print(now)
plan_expirary = now + relativedelta(months=+MONTHS)
print(plan_expirary)
