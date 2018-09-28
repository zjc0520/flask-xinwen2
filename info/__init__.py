from logging.handlers import RotatingFileHandler
import redis
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_session import Session
from config import config_dict
import logging

#modules包括所有模块，index文件夹代表一个模块，
# config文件用于项目初始化配置
# index下的__init__用于注册蓝图，views实现模块功能
# info用于做业务逻辑，
# info下的__init__.py用于注册app.
# manager用于启动项目
# logs文件夹是用于储存日志
# static是放静态文件
#templates放模板文件


#初始化数据库配置
db=SQLAlchemy()
# redis数据库对象的声明(全局变量)
redis_store=None

def setup_log(config_name):
    """配置日志"""
    # 设置日志的记录等级
    logging.basicConfig(level=config_dict[config_name].LOG_LEVEL)  # 调试debug级别
    # 创建日志记录器，指明日志保存的路径、每个日志文件的最大大小、保存的日志文件个数上限
    file_log_handler = RotatingFileHandler("logs/log", maxBytes=1024 * 1024 * 100, backupCount=10)
    # 创建日志记录的格式 日志等级 输入日志信息的文件名 行数 日志信息
    formatter = logging.Formatter('%(levelname)s %(filename)s:%(lineno)d %(message)s')
    # 为刚创建的日志记录器设置日志记录格式
    file_log_handler.setFormatter(formatter)
    # 为全局的日志工具对象（flask app使用的）添加日志记录器
    logging.getLogger().addHandler(file_log_handler)

def create_app(config_name):
    """通过传入不同的配置名字，初始化其对应配置的应用实例"""
    # 配置项目日志
    setup_log(config_name)
    app=Flask(__name__)
    # 配置
    app.config.from_object(config_dict[config_name])
    # 创建数据库对象，烂加载
    db.init_app(app)
    # 配置redis
    global redis_store
    redis_store = redis.StrictRedis(host=config_dict[config_name].REDIS_HOST, port=config_dict[config_name].REDIS_PORT)
    # 开启csrf保护
    """
        #4.开启csrf保护机制
        1.自动获取cookie中的csrf_token,
        2.自动获取ajax请求头中的csrf_token
        3.自己校验这两个值
        """
    CSRFProtect(app)
    # 设置session保存位置
    Session(app)
    # 注册蓝图
    from info.modules.index import index_blu
    # 注册首页的蓝图对象
    app.register_blueprint(index_blu)
    #返回不同模式下的app对象
    return app
