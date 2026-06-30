import yt_dlp
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/info', methods=['GET'])
def get_info():
    url = request.args.get('url')
    ydl_opts = {
        'simulate': True,
        'dump_single_file': True,
        'get_title': True,
        'get_description': True,
        'get_thumbnail': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return jsonify(info)

if __name__ == '__main__':
    app.run(debug=True)