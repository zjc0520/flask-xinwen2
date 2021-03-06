import redis
import logging

class Config(object):
    """工程配置信息"""
    SECRET_KEY="ERIQWPOETIPQWOTY"

    DEBUG=True

    #数据库配置信息
    SQLALCHEMY_DATABASE_URI='mysql://root:mysql@127.0.0.1:3306/newsinformation'
    SQLALCHEMY_TRACK_MODIFICATIONS=True

    # redis配置
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379
    REDIS_NUM = 9


    # session 配置
    SESSION_TYPE = "redis"  # 指定 session 保存到 redis 中
    SESSION_USE_SIGNER = True  # 让 cookie 中的 session_id 被加密签名处理
    SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)  # 使用 redis 的实例
    # 关闭永久存储
    SESSION_PERMANENT = False
    PERMANENT_SESSION_LIFETIME = 86400# session 的有效期# ，单位是秒


class DevelopementConfig(Config):
    """开发模式下的配置"""
    DEBUG = True
    LOG_LEVEL=logging.DEBUG


class ProductionConfig(Config):
    """生产模式下的配置"""
    LOG_LEVEL=logging.WARNING

# 定义配置字典
# 给外界暴露一个使用配置类的接口
# 使用方法： config_dict['development'] --> DevelopmentConfig 开发环境的配置类
config_dict = {
    "development": DevelopementConfig,
    "production": ProductionConfig
}


