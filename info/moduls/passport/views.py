from datetime import datetime
from flask import current_app, jsonify, abort, session
from flask import make_response
from flask import request
from flask import render_template

from info import constants, db
from info import redis_store
from info.models import User
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET
import re, random
import logging
from info.lib.yuntongxin.sms import CCP

from . import passport_blu
@passport_blu.route('/image_code')
def get_image_code():
    """获取验证码图片的后端接口"""
    """
    1.获取参数
        1.1获取code_id,全球唯一的编码（uuid）
    2.效验参数
        2.1,非空判断，判断code_id是否有值
    3.逻辑处理
        3.1 生成验证码图片&生成验证码图片的真实值（文子）
        3.2 以code_id作为key 将生成验证码图片的真实值（文字）
        存储到redis数据库
    4.返回值
        4.1返回验证码图片
    """


    # 1.1获取code_id, 全球唯一的编码（uuid）
    code_id=request.args.get("code_id",'')
    #2.1非空判断，判断code_id是否有值
    if not code_id:
        current_app.logger.error("参数不足")
        # 参数不存在404错误
        abort(404)
    # 3.1生成验证码图片 & 生成验证码图片的真实值（文子）
    image_name,real_image_code,image_data=captcha.generate_captcha()
    #3.2 以code_id作为key 将生成验证码图片的真实值（文字）
    # 存储到redis数据库
    try:
        redis_store.setex("imageCodeId_%s" % code_id,constants.IMAGE_CODE_REDIS_EXPIRES,real_image_code)
    except Exception as e:
        current_app.logger.error(e)
        abort(500)
    # 4.1返回验证码图片(二进制图片数据，不能兼容所有浏览器)
    # 创建响应对象
    response=make_response(image_data)
    response.headers["Content-Type"]="image/JPEG"
    return response
#发送短信后端实现
@passport_blu.route('/sms_code',methods=['POST'])
def send_sms_code():
    """点击发送短信验证码后端接口"""
    """
    1.获取参数
        1.1.用户账号手机号码mobile, 
        用户填写的图片验证码值：image_code，
         编号UUID:image_code_id
    2.效验参数
        2.1非空判断 mobile,image_code，image_code_id 是否有空
        2.2手机号码格式的正则判断
    3.逻辑处理
        3.1 根据编号去redis数据库获取图片验证码的真实值（正确值）
            3.1.1 真实值有值: 将这个值从redis中删除（防止他人多次拿着同一个验证码值来验证）
             3.1.2 真实值没有值： 图片验证码真实值过期了
        3.2 拿用户填写的图片验证码值和Redis中获取的真实值进行比较
        3.3 不相等 告诉前端图片验证码填写错误
        TODO: 判断用户是否注册过,如果注册过，就不在发送短信验证码引导到登录页（提高用户体验）
        3.4 相等， 生成6位随机短信验证码，发送短信验证码
        3.5 将 生成6位随机短信验证码存储到redis数据库
     4.返回值
        4.1 发送短信验证码成功
    """
    # 1.1.用户账号手机号码mobile,
    # 用户填写的图片验证码值：image_code，编号UUID:image_code_id
    # json.loads(request.data)
    # 可以接受前端上传的json格式数据，json字符串转换成python对象
    param_dict=request.json
    # 手机号码
    mobile=param_dict.get("mobile",'')
    # 用户填写的图片验证码值
    image_code=param_dict.get("image_code",'')
    #UUid编号
    image_code_id=param_dict.get('image_code_id','')

    print('77777')
    # 2.1 非空判断 mobile,image_code，image_code_id 是否有空
    if not all([mobile,image_code,image_code_id]):
        # 记录日志
        current_app.logger.error("参数不足")
        # 给调用者返回json格式的错误信息
        return jsonify({"errno":RET.PARAMERR,"errmsg": '参数不足'})
    #2.2手机号码格式的正则判断
    if not re.match("1[35789][0-9]{9}",mobile):
        current_app.logger.error("手机格式错误")
        return jsonify(errno=RET.PARAMERR, errmsg="手机格式错误")
    #3.1,根据编号去redis数据库获取图片验证码的真实值（正确值）
    try:
        real_image_code=redis_store.get("imageCodeId_%s" % image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="从redis中获取图片真实值异常")
    #3.1.1 真实值有值: 将这个值从redis中删除（防止他人多次拿着同一个验证码值来验证）
    if real_image_code:
        redis_store.delete("imageCodeId_%s" % image_code_id)
    # 3.1.2 真实值没有值： 图片验证码真实值过期了
    else:
        return jsonify(error=RET.NODATA,errmsg="图片验证码过期")
    # 3.2 拿用户填写的图片验证码值和Redis中获取的真实值进行比较
    # 细节1：全部按照小写格式进行比较（忽略大小写）
    # 细节2：redis对象创建的时候设置decode_responses=True
    if real_image_code.lower()!=image_code.lower():
        # 3.3 不相等 告诉前端图片验证码填写错误
        return jsonify(errno=RET.DATAERR, errmsg="填写图片验证码错误")
    # TODO: 判断用户是否注册过,如果注册过，就不在发送短信验证码引导到登录页（提高用户体验
    try:
        user=User.query.filter(User.mobile==mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="从mysql中查询用户异常")
    # 注册过就不在发送短信验证码引导到登录页
    if user:
        return jsonify(errno=RET.DATAEXIST, errmsg="手机号码已经注册")
    # 3.4 相等， 生成6位随机短信验证码，发送短信验证码
    # 生成6位随机短信验证码
    sms_code=random.randint(0,999999)
    # 不足6位前面补0
    sms_code = "%06d" % sms_code
    try:
        result = CCP().send_template_sms(mobile, {sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60}, 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="云通讯发送短信失败")
    if result != 0:
        return jsonify(errno=RET.THIRDERR, errmsg="云通讯发送短信失败")

        # 3.4 将 生成6位随机短信验证码存储到redis数据库
    try:
        # SMS_CODE_18520340804 每个用户这个key都不一样
        redis_store.setex("SMS_CODE_%s" % mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="存储短信验证码异常")

        # 4.返回值
    return jsonify(errno=RET.OK, errmsg="发送短信验证码成功，注意查收")
@passport_blu.route('/register',methods=['POST'])
def register():
    """注册页面后端实现"""

    """
    1.获取参数：手机号mobile,手机验证码，密码
    2.效验参数
    3.从redis中取出指定手机号对应的验证码
    4.效验验证码
    5,初始化user模型,并设置数据添加到数据库
    6. 保存当前用户的状态
    7. 返回注册的结果
    """
    # 1.获取参数：手机号mobile, 手机验证码，密码
    json_data=request.json
    mobile=json_data.get("mobile",'')
    sms_code=json_data.get("smscode",'')
    password=json_data.get("password",'')
    # 2.效验参数
    # 2.1非空验证
    if not all([mobile,sms_code,password]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    #2.2，手机号验证
    if not re.match("1[35789][0-9]{9}",mobile):
        current_app.logger.error("手机格式错误")
        return jsonify(errno=RET.PARAMERR, errmsg="手机格式错误")
    # 3.从redis中取出指定手机号对应的验证码
    try:
        real_sms_code=redis_store.get("SMS_CODE_"+mobile)
    except Exception as e:
        current_app.logger.error(e)
        # 获取本地验证码失败
        return jsonify(errno=RET.DBERR, errmsg="获取本地验证码失败")
    if not real_sms_code:
        # 短信验证码过期
        return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")
    # 4. 效验验证码
    if sms_code!=real_sms_code:
        return jsonify(errno=RET.PARAMERR,errmsg="短信验证码错误")
    # 删除短信验证码
    try:
        redis_store.delete("SMS_CODE_"+mobile)
    except Exception as e:
        current_app.logger.error(e)
    # 5, 初始化user模型, 并设置数据添加到数据库
    user=User()
    user.nick_name=mobile
    user.mobile=mobile
    # 当前时间作为最后一次登录时间
    user.last_login = datetime.now()
    # TODO: 密码加密处理
    # 一般的套路
    # user.set_password_hash(password)
    # 将属性赋值的底层实现（复习）
    user.password=password
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        # 数据保存错误
        return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")
    # 6. 保存用户登录状态
    session["user_id"]=user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    # 7. 返回注册结果
    return jsonify(errno=RET.OK, errmsg="OK")
@passport_blu.route('/login', methods=["POST"])
def login():
     """登录后端实现"""
     """
     1.获取参数：手机号mobile，密码，possword
     2.效验参数
     3. 从数据库查询出指定的用户
     4. 校验密码
     5. 保存用户登录状态
     6. 返回结果
     """
     # 1. 获取参数和判断是否有值
     json_data=request.json
     mobile=json_data.get("mobile")
     password=json_data.get("password")
     # 2.效验参数
     if not all([mobile,password]):
         #参数不全
        return jsonify(error=RET.PARAMERR,errmsg="参数不齐")
     # 2.2 手机号码格式判断
     if not re.match('1[35789][0-9]{9}', mobile):
         current_app.logger.error("手机格式错误")
         return jsonify(errno=RET.PARAMERR, errmsg="手机格式错误")
     # 3.从数据库查询出指定的用户
     try:
        user=User.query.filter(User.mobile==mobile).first()
     except Exception as e:
         current_app.logger.error(e)
         return jsonify(errno=RET.DBERR, errmsg="查询数据错误")

     if not user:
         return jsonify(error=RET.USERERR,errmsg="用户不存在")
     #4.效验密码
     if not user.check_passowrd(password):
         return jsonify(errno=RET.PWDERR, errmsg="密码错误")
     #5.保存用户登录状态
     session["user_id"]=user.id
     session['nick_name']=user.nick_name
     session["mobile"]=user.mobile
     #记录用户最后一次登录时间
     user.last_login=datetime.now()
     # 修改了user对象的数据，需要使用commit将数据保存到数据库
     try:
         db.session.commit()
     except Exception as e:
         current_app.logger.error(e)
         db.session.rollback()
         #数据库回滚
         return jsonify(errno=RET.DBERR, errmsg="保存用户数据异常")
     # 4.登录成功
     return jsonify(errno=RET.OK, errmsg="登录成功")








