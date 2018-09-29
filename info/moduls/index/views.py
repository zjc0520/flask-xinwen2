from . import index_blu
from flask import render_template, current_app


# 使用蓝图
@index_blu.route('/index')
def index():
    return render_template("news/index.html")
@index_blu.route('/favicon.ico')
def favicon():
    #返回静态文件给浏览器
    return current_app.send_static_file('news/favicon.ico')

