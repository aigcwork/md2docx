import os
import uuid
import subprocess
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

# -----------------------------------------------------------------------------
# 1. 初始化 Flask 应用
# -----------------------------------------------------------------------------
# 创建 Flask app 实例
app = Flask(__name__)

# 使用 Flask-Cors 扩展来处理跨域请求，允许任何来源访问我们的 API
CORS(app)

# -----------------------------------------------------------------------------
# 2. 定义临时文件存储目录
# -----------------------------------------------------------------------------
# 函数计算环境的可写目录是 /tmp
# 我们将在这里存放转换过程中的临时 .md 和 .docx 文件
TEMP_DIR = '/tmp'

# -----------------------------------------------------------------------------
# 3. 创建核心的 API 转换接口
# -----------------------------------------------------------------------------
# 定义一个 API 路由，地址为 /api/convert，只接受 POST 方法的请求
@app.route('/api/convert', methods=['POST'])
def convert_markdown_to_docx():
    """
    接收 Markdown 文本，使用 Pandoc 将其转换为 DOCX 文件，并返回该文件。
    """
    # --- 安全检查：确保收到的数据是 JSON 格式 ---
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    # --- 获取请求中的 Markdown 内容 ---
    data = request.get_json()
    markdown_content = data.get('markdown')

    if not markdown_content:
        return jsonify({"error": "Missing 'markdown' key in request body"}), 400

    # --- 创建唯一的临时文件名，避免并发请求时文件冲突 ---
    # 使用 uuid 生成一个随机的、几乎不可能重复的字符串
    unique_id = str(uuid.uuid4())
    input_md_path = os.path.join(TEMP_DIR, f'{unique_id}.md')
    output_docx_path = os.path.join(TEMP_DIR, f'{unique_id}.docx')

    # --- 使用 try...finally 结构确保临时文件总能被清理 ---
    try:
        # --- 将收到的 Markdown 内容写入临时文件 ---
        # 使用 utf-8 编码以支持中文和各种特殊符号
        with open(input_md_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        # --- 构建并执行 Pandoc 命令行指令 ---
        command = [
            'pandoc',
            input_md_path,
            '-o',
            output_docx_path
        ]
        
        # 使用 subprocess.run 执行命令，这是更现代、更安全的方式
        # timeout=30: 设置30秒超时，防止 pandoc 因异常输入而卡死
        result = subprocess.run(
            command, 
            capture_output=True,  # 捕获标准输出和标准错误
            text=True,            # 以文本形式解码输出
            timeout=30
        )

        # --- 检查 Pandoc 是否成功执行 ---
        # 如果 result.returncode 不为 0，说明 pandoc 执行失败
        if result.returncode != 0:
            # 将 pandoc 的错误信息返回给前端，方便排查问题
            print("Pandoc Error:", result.stderr) # 在函数计算日志中打印错误
            return jsonify({
                "error": "Pandoc conversion failed",
                "details": result.stderr
            }), 500

        # --- 检查输出文件是否存在 ---
        if not os.path.exists(output_docx_path):
             return jsonify({"error": "Converted file not found on server"}), 500

        # --- 成功，将生成的 DOCX 文件作为附件发回给客户端 ---
        return send_file(
            output_docx_path,
            as_attachment=True,
            # 这是用户下载时看到的文件名
            download_name='converted_document.docx',
            # 这是标准的 docx 文件 MIME 类型
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )

    finally:
        # --- 清理战场：删除临时文件 ---
        # 无论转换成功还是失败，这个代码块都会执行
        if os.path.exists(input_md_path):
            os.remove(input_md_path)
        if os.path.exists(output_docx_path):
            os.remove(output_docx_path)

# 注意：在函数计算环境中，我们不需要 app.run()
# Gunicorn 会直接从 Dockerfile 的 CMD 指令启动 app。
# 下面的代码块仅用于本地测试，在生产环境中不会被执行。
if __name__ == '__main__':
    # 在本地 5001 端口上以调试模式运行
    app.run(host='0.0.0.0', port=5001, debug=True)