from flask import current_app, jsonify, abort
from flask import make_response
from flask import request

from info import constants
from info import redis_store
from info.models import User
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET
import re, random
import logging
from info.lib.yuntongxun.sms import CCP

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
@passport_blu.route('/smscode',methods=['POST'])
def send_sms():
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






