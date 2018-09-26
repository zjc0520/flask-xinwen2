from flask import Flask

app=Flask(__name__)

@app.route('/')
def index():
    return 'helloworld'
@app.route('/')
def index():
    return 'helloworld'

if __name__ == '__main__':
    app.run(debug=True)