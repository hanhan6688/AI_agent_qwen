#!/usr/bin/env python3
"""
批量上传测试脚本
测试批量PDF上传功能
"""

import requests
import os
import sys

def test_batch_upload():
    """测试批量上传"""
    print("=" * 60)
    print("批量上传功能测试")
    print("=" * 60)

    # API地址
    base_url = "http://localhost:8080"
    login_url = f"{base_url}/api/auth/login"
    upload_url = f"{base_url}/api/tasks"

    # 1. 登录
    print("\n[1/3] 登录系统...")
    try:
        login_data = {
            "username": "admin",
            "password": "admin123"
        }
        response = requests.post(login_url, json=login_data, timeout=10)
        if response.status_code == 200:
            user_data = response.json().get('data', {})
            user_id = user_data.get('userId')
            token = response.json().get('data', {}).get('token')
            print(f"✅ 登录成功，用户ID: {user_id}")
        else:
            print(f"❌ 登录失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return False

    # 2. 查找测试PDF文件
    print("\n[2/3] 查找测试PDF文件...")
    test_files = []
    data_dir = "data/uploads"

    if os.path.exists(data_dir):
        for file in os.listdir(data_dir):
            if file.lower().endswith('.pdf'):
                test_files.append(os.path.join(data_dir, file))
                if len(test_files) >= 3:  # 最多测试3个文件
                    break

    if not test_files:
        print("⚠️  未找到PDF测试文件，将创建模拟上传请求")
        # 创建模拟数据
        test_files = ["模拟文件1.pdf", "模拟文件2.pdf"]

    print(f"✅ 找到 {len(test_files)} 个测试文件")
    for i, f in enumerate(test_files, 1):
        print(f"   {i}. {os.path.basename(f)}")

    # 3. 批量上传测试
    print("\n[3/3] 测试批量上传接口...")
    try:
        # 准备表单数据
        form_data = {
            'taskName': '批量测试任务',
            'userId': str(user_id),
            'extractFields': '[{"name": "测试字段1", "description": "测试描述1"}, {"name": "测试字段2", "description": "测试描述2"}]'
        }

        # 准备文件（如果有真实文件）
        files = []
        for file_path in test_files:
            if os.path.exists(file_path):
                files.append(('files', (os.path.basename(file_path), open(file_path, 'rb'), 'application/pdf')))

        # 发送请求
        print(f"   请求URL: {upload_url}")
        print(f"   表单数据: {form_data}")

        response = requests.post(upload_url, data=form_data, files=files if files else None, timeout=30)

        # 关闭文件
        for _, file_tuple in files:
            file_tuple[1].close()

        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                tasks = result.get('data', [])
                print(f"✅ 批量上传成功！创建 {len(tasks)} 个任务")
                for task in tasks:
                    print(f"   - 任务ID: {task.get('taskId')}, 文件名: {task.get('fileName')}")
                return True
            else:
                print(f"❌ 业务逻辑失败: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"   响应: {response.text}")
            return False

    except Exception as e:
        print(f"❌ 上传异常: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_services():
    """检查服务状态"""
    print("\n" + "=" * 60)
    print("服务状态检查")
    print("=" * 60)

    services = [
        ("Redis", "http://localhost:8080/api/tasks", 5),
        ("后端API", "http://localhost:8080/api/tasks", 5),
    ]

    all_ok = True
    for name, url, timeout in services:
        try:
            if name == "Redis":
                # 检查Redis
                import redis
                r = redis.Redis(host='localhost', port=6379, password='redis123', decode_responses=True)
                if r.ping():
                    print(f"✅ Redis: 运行正常")
                else:
                    print(f"❌ Redis: 连接失败")
                    all_ok = False
            else:
                # 检查后端
                response = requests.get(url, timeout=timeout)
                if response.status_code in [200, 401, 403]:
                    print(f"✅ {name}: 运行正常")
                else:
                    print(f"❌ {name}: 状态异常 ({response.status_code})")
                    all_ok = False
        except Exception as e:
            print(f"❌ {name}: 连接失败 - {e}")
            all_ok = False

    return all_ok

def main():
    """主函数"""
    print("文档智能提取系统 - 批量上传功能测试")
    print("此脚本将测试批量PDF上传功能")
    print()

    # 检查服务
    if not check_services():
        print("\n⚠️  某些服务未正常运行，请确保所有服务已启动")
        print("   可以运行: start-all.bat")
        sys.exit(1)

    # 测试批量上传
    success = test_batch_upload()

    print("\n" + "=" * 60)
    if success:
        print("✅ 测试完成！批量上传功能正常工作")
        print("\n下一步:")
        print("1. 打开浏览器访问 http://localhost:5173")
        print("2. 使用用户名: admin, 密码: admin123 登录")
        print("3. 在Dashboard页面上传多个PDF文件测试")
    else:
        print("❌ 测试失败，请检查错误信息")
        sys.exit(1)
    print("=" * 60)

if __name__ == "__main__":
    # 安装所需库
    try:
        import requests
        import redis
    except ImportError:
        print("正在安装所需库...")
        os.system("pip install requests redis")
        import requests
        import redis

    main()
