import socket
import os
import json
from threading import Thread
import Queue
import signal

import plasmatrim
import web
from zeroconf import Zeroconf, ServiceInfo

class Home:
    def GET(self):
        plasma = web.ctx['plasma']
        led = plasma.leds[0]
        color = [ led[0], led[1], led[2] ]
        return web.ctx['render'].index(color)

class API_Color:
    def GET(self):
        web.header('Content-Type', 'application/json')
        
        plasma = web.ctx['plasma']
        led = plasma.leds[0]
        color = [ led[0], led[1], led[2] ]
        return json.dumps(color)

    def POST(self):
        web.header('Content-Type', 'application/json')
        
        plasma = web.ctx['plasma']
        color = json.loads(web.data())
        if len(color) != 3:
            return json.dumps({ 'status': 'Error', 'error': 'Invalid number of colors. Should be 3 (rgb)' })
        for i, led in enumerate(plasma.leds):
            for j, index in enumerate(led):
                led[j] = color[j]
        web.ctx['callback_queue'].put(plasma.leds.show)
        return json.dumps({ 'status': 'OK' })

class API_Brightness:
    def GET(self):
        web.header('Content-Type', 'text/plain')
        
        plasma = web.ctx['plasma']
        return plasma.brightness
    
    def POST(self):
        web.header('Content-Type', 'application/json')
        
        brightness = int(web.data())
        plasma = web.ctx['plasma']
        plasma.brightness = min(100, max(0, brightness))
        web.ctx['callback_queue'].put(plasma.leds.show)
        return json.dumps({ 'status': 'OK' })
        

class Server:
    def run(self):
        self.find_plasma_trim()
        self.register_service()
        self.run_web_server()
        self.write_plasma_trim_changes()
    
    def find_plasma_trim(self):
        plasmas = plasmatrim.find()
        self.plasma = plasmas[0]
    
    def register_service(self):
        ip_address = socket.gethostbyname(socket.gethostname())
        type = "_radiance._tcp.local."
        hostname = socket.gethostname()
        split_index = hostname.find(".local")
        if split_index > 0:
            hostname = hostname[:split_index]
        name = str("%s.%s") % (hostname, type)
        self.service = ServiceInfo(type, name, socket.inet_aton(ip_address), 8080, 0, 0, str())
        
        self.zeroconf = Zeroconf()
        self.zeroconf.register_service(self.service)
    
    def run_web_server(self):
        self.render = web.template.render('templates/')
        
        urls = (
            '/', 'Home',
            '/api/color', 'API_Color',
            '/api/brightness', 'API_Brightness'
        )
        self.app = web.application(urls, globals())
        self.app.add_processor(web.loadhook(self.load_plasma_trim))
        self.app.add_processor(web.loadhook(self.load_renderer))
        self.app.add_processor(web.loadhook(self.load_main_thread_queue))
        
        self.web_server_thread = Thread(None, self.app.run)
        self.web_server_thread.start()
    
    def write_plasma_trim_changes(self):
        signal.signal(signal.SIGINT, self.handle_ctrl_c)
        self.callback_queue = Queue.Queue()
        while True:
            callback = self.callback_queue.get()
            callback()
    
    def load_plasma_trim(self):
        web.ctx['plasma'] = self.plasma
    
    def load_renderer(self):
        web.ctx['render'] = self.render
    
    def load_main_thread_queue(self):
        web.ctx['callback_queue'] = self.callback_queue
    
    def handle_ctrl_c(self):
        print "Exiting"
        sys.exit(0)

if __name__ == "__main__":
    Server().run()
