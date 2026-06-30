from flask import Flask
import sanctuary_command_center as scc

app = Flask(__name__)

@app.route('/api/info', methods=['GET'])
def api_info():
    return scc.get_info()

@app.route('/api/download', methods=['POST'])
def api_download():
    return scc.download_video()

if __name__ == '__main__':
    app.run(port=5001)