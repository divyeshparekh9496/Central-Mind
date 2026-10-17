"""Run the space clubhouse without cloud dependencies: python adventure_server.py."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from services.adventure import AdventureService

ROOT=Path(__file__).resolve().parent


def make_handler(service):
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,payload,status=200):
            raw=json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers();self.wfile.write(raw)

        def do_GET(self):
            path=urlparse(self.path)
            if path.path=='/':
                body=(ROOT/'static/index.html').read_bytes()
                self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            elif path.path=='/adventure/missions':self.send_json({'missions':service.missions()})
            elif path.path=='/adventure/state':
                try:self.send_json(service.state(parse_qs(path.query).get('session_id',[''])[0]))
                except ValueError as error:self.send_json({'detail':str(error)},400)
            else:self.send_json({'detail':'Not found'},404)

        def do_POST(self):
            try:
                length=int(self.headers.get('Content-Length',0))
                if not 0 < length <= 8192:raise ValueError('Invalid request size.')
                body=json.loads(self.rfile.read(length))
                if not isinstance(body,dict):raise ValueError('Expected a JSON object.')
                if self.path=='/adventure/quiz':result=service.start(body['session_id'],body['topic'])
                elif self.path=='/adventure/answer':result=service.answer(body['session_id'],body['attempt_id'],body['choice'])
                elif self.path=='/adventure/forget':result=service.forget(body['session_id'])
                elif self.path=='/adventure/ask':
                    query=body.get('query','')
                    if not isinstance(query,str) or not 1 <= len(query) <= 500:raise ValueError('Ask a short space question.')
                    if body.get('live'):
                        self.send_json({'detail':'Connected research needs the configured cloud app. You can keep exploring with the local guide.'},503);return
                    result=service.guide(query,body.get('topic','planets'))
                else:self.send_json({'detail':'Not found'},404);return
                self.send_json(result)
            except (ValueError,KeyError,TypeError) as error:self.send_json({'detail':str(error)},400)

        def log_message(self,format,*args):
            # Do not write request URLs (including session IDs) into an access log.
            pass
    return Handler


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',type=int,default=8000)
    p.add_argument('--db',default=str(ROOT/'data/adventure.sqlite3'))
    args=p.parse_args()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),make_handler(AdventureService(args.db)))
    print(f'Central Mind Space Club: http://127.0.0.1:{args.port}',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()


if __name__=='__main__':main()
