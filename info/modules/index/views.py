from . import index_blu
# 使用蓝图
@index_blu.route('/index')
def index():
    return 'index'