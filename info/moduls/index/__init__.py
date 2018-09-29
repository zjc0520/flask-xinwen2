from flask import Blueprint
# 1.注册蓝图
index_blu=Blueprint("index",__name__)
# nihao.延迟导入
from . import views