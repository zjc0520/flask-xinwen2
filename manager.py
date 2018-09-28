from flask_script import Manager
from flask_migrate import Migrate,MigrateCommand
from info import create_app, db
from info import models
from flask import current_app

"""
从单一职责的思想考虑：manage.py文件仅仅作为项目启动文件即可，其余配置全部抽取出去
"""
# ofo公司 调用工厂方法
"""manager只做项目启动"""
app=create_app("development")
# Flask-script
manager=Manager(app)

#数据库迁移
Migrate(app,db)
manager.add_command("db",MigrateCommand)

if __name__ == '__main__':
    manager.run()