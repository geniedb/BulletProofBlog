CELERY_IMPORTS = ("provision.tasks", )
BROKER_URL = "amqp://guest:guest@localhost:5672/"
CELERY_TASK_RESULT_EXPIRES = 600
