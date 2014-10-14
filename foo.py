from celery import Celery

app = Celery('tasks', backend='redis://localhost', broker='redis://localhost:6379/0')

@app.task
def add(x, y):
    return x + y

def hello():
    return 'hello world'
