CELERY_IMPORTS = ("provision.tasks", )
BROKER_URL = "amqp://guest:guest@localhost:5672/"
CELERY_TASK_RESULT_EXPIRES = 600
CELERYD_TASK_TIME_LIMIT = 1000
CELERYD_TASK_SOFT_TIME_LIMIT = 900
