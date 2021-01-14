#!/usr/bin/python

# BSD Licensed, Copyright (c) 2006-2008 MetaCarta, Inc.

import sys, os, traceback
import cgi as cgimod
import urllib.request, urllib.parse, urllib.error
import io


class ApplicationException(Exception): 
    """Any application exception should be subclassed from here. """
    status_code = 500
    status_message = "Error"
    def get_error(self):
        """Returns an HTTP Header line: a la '500 Error'""" 
        return "%s %s" % (self.status_code, self.status_message)

def binary_print(binary_data):
    """This function is designed to work around the fact that Python
       in Windows does not handle binary output correctly. This function
       will set the output to binary, and then write to stdout directly
       rather than using print."""
    try:
        import msvcrt
        msvcrt.setmode(sys.__stdout__.fileno(), os.O_BINARY)
    except:
        # No need to do anything if we can't import msvcrt.  
        pass
    sys.stdout.write(binary_data)    

def mod_python (dispatch_function, apache_request):
    """mod_python handler."""    
    from mod_python import apache, util
    
    try:
        if "X-Forwarded-Host" in apache_request.headers_in:
            base_path = "http://" + apache_request.headers_in["X-Forwarded-Host"]
        else:
            base_path = "http://" + apache_request.headers_in["Host"]
            
        base_path += apache_request.uri[:-len(apache_request.path_info)]
        accepts = "" 
        if "Accept" in apache_request.headers_in:
            accepts = apache_request.headers_in["Accept"]
        elif "Content-Type" in apache_request.headers_in:
            accepts = apache_request.headers_in["Content-Type"]
        
        post_data = apache_request.read()
        request_method = apache_request.method

        params = {}
        if request_method != "POST":
            fields = util.FieldStorage(apache_request) 
            for key in list(fields.keys()):
                params[key.lower()] = fields[key] 
        returned_data = dispatch_function( 
          base_path = base_path, 
          path_info = apache_request.path_info, 
          params = params, 
          request_method = request_method, 
          post_data = post_data, 
          accepts = accepts )
        
        if isinstance(returned_data, list) or isinstance(returned_data, tuple): 
            format, data = returned_data[0:2]
            if len(returned_data) == 3:
                for key, value in list(returned_data[2].items()):
                    apache_request.headers_out[key] = value

            apache_request.content_type = format
            apache_request.send_http_header()
            apache_request.write(data)
        else:
            obj = returned_data
            if obj.extra_headers:
                for key, value in list(obj.extra_headers.items()):
                    apache_request.headers_out[key] = value

            apache_request.status = obj.status_code
            apache_request.content_type = obj.content_type
            apache_request.send_http_header()
            apache_request.write(obj.getData())

    except ApplicationException as error:
        apache_request.content_type = "text/plain"
        apache_request.status = error.status_code 
        apache_request.send_http_header()
        apache_request.write("An error occurred: %s\n" % (str(error)))
    except Exception as error:
        apache_request.content_type = "text/plain"
        apache_request.status = apache.HTTP_INTERNAL_SERVER_ERROR
        apache_request.send_http_header()
        apache_request.write("An error occurred: %s\n%s\n" % (
            str(error), 
            "".join(traceback.format_tb(sys.exc_info()[2]))))
    
    return apache.OK

def wsgi (dispatch_function, environ, start_response):
    """handler for wsgiref simple_server"""
    try:
        path_info = base_path = ""

        if "PATH_INFO" in environ: 
            path_info = environ["PATH_INFO"]

        if "HTTP_X_FORWARDED_HOST" in environ:
            base_path      = "http://" + environ["HTTP_X_FORWARDED_HOST"]
        elif "HTTP_HOST" in environ:
            base_path      = "http://" + environ["HTTP_HOST"]

        base_path += environ["SCRIPT_NAME"]
        
        accepts = None 
        if "CONTENT_TYPE" in environ:
            accepts = environ['CONTENT_TYPE']
        else:
            accepts = environ.get('HTTP_ACCEPT', '')

        request_method = environ["REQUEST_METHOD"]
        
        params = {}
        post_data = None
    
        if 'CONTENT_LENGTH' in environ and environ['CONTENT_LENGTH']:
            post_data = environ['wsgi.input'].read(int(environ['CONTENT_LENGTH']))            
    
        if 'QUERY_STRING' in environ:
            for key, value in urllib.parse.parse_qsl(environ['QUERY_STRING'], keep_blank_values=True):
                params[key.lower()] = value
        
        returned_data = dispatch_function( 
          base_path = base_path, 
          path_info = path_info, 
          params = params, 
          request_method = request_method, 
          post_data = post_data, 
          accepts = accepts )
        
        if isinstance(returned_data, list) or isinstance(returned_data, tuple): 

            format, data = returned_data[0:2]
            headers = {'Content-Type': format}
            if len(returned_data) == 3:
                headers.update(returned_data[2])
                  
            start_response("200 OK", list(headers.items()))
            return [bytes(data)]
        else:
            # This is a a web_request.Response.Response object
            headers = {'Content-Type': returned_data.content_type}
            if returned_data.extra_headers:
                headers.update(returned_data.extra_headers)
            start_response("%s Message" % returned_data.status_code,
                           list(headers.items()))
            
            return [returned_data.getData()]


    except ApplicationException as error:
        start_response(error.get_error(), [('Content-Type', 'text/plain')])
        msg = f"An error occurred: {str(error)}" 
        return msg.encode('utf-8')
    except Exception as error:
        start_response("500 Internal Server Error", [('Content-Type', 'text/plain')])
        trace = "".join(traceback.format_tb(sys.exc_info()[2]))
        msg = f"An error occurred: {str(error)}\n{trace}\n" 
        return [msg.encode('utf-8')]

def cgi (dispatch_function):
    """cgi handler""" 

    try:
        accepts = ""
        if "CONTENT_TYPE" in os.environ:
            accepts = os.environ['CONTENT_TYPE']
        elif "HTTP_ACCEPT" in os.environ:
            accepts = os.environ['HTTP_ACCEPT']
        
        request_method = os.environ["REQUEST_METHOD"]
        content_length = int(os.environ["CONTENT_LENGTH"])
        
        post_data = None 
        params = {}
        if request_method != "GET" and request_method != "DELETE":
            if content_length:
                # IIS doesn't seem to provide EOF
                post_data = sys.stdin.read(content_length)   
            else:
                # would we ever not have content length?
                post_data = sys.stdin.read()
            
            
            # StringIO to create filehandler so data can be read again by cgi 
            fields = cgimod.FieldStorage(fp=io.StringIO(post_data))
            if fields != None:
                for key, value in urllib.parse.parse_qsl(fields.qs_on_post, keep_blank_values=True):
                    params[key.lower()] = value
            
                
        else:
            fields = cgimod.FieldStorage()
            try:
                for key in list(fields.keys()): 
                    params[key.lower()] = urllib.parse.unquote(fields[key].value)
            except TypeError:
                pass
    
        path_info = base_path = ""

        if "PATH_INFO" in os.environ: 
            path_info = os.environ["PATH_INFO"]

        if "HTTP_X_FORWARDED_HOST" in os.environ:
            base_path      = "http://" + os.environ["HTTP_X_FORWARDED_HOST"]
        elif "HTTP_HOST" in os.environ:
            base_path      = "http://" + os.environ["HTTP_HOST"]

        base_path += os.environ["SCRIPT_NAME"]
        
        returned_data = dispatch_function( 
          base_path = base_path, 
          path_info = path_info, 
          params = params, 
          request_method = request_method, 
          post_data = post_data, 
          accepts = accepts )
        
        if isinstance(returned_data, list) or isinstance(returned_data, tuple): 
            format, data = returned_data[0:2]
            
            if len(returned_data) == 3:
                for (key, value) in list(returned_data[2].items()):
                    print("%s: %s" % (key, value))

            print("Content-type: %s\n" % format)

            if sys.platform == "win32":
                binary_print(data)
            else:    
                print(data) 
        
        else:    
            # Returned object is a 'response'
            obj = returned_data
            if obj.extra_headers:
                for (key, value) in list(obj.extra_headers.items()): 
                    print("%s: %s" % (key, value))

            print("Content-type: %s\n" % obj.content_type)

            if sys.platform == "win32":
                binary_print(obj.getData())
            else:    
                print(obj.getData())
    
    except ApplicationException as error:
        print("Cache-Control: max-age=10, must-revalidate") # make the client reload        
        print("Content-type: text/plain\n")
        print("An error occurred: %s\n" % (str(error)))
    except Exception as error:
        print("Cache-Control: max-age=10, must-revalidate") # make the client reload        
        print("Content-type: text/plain\n")
        print("An error occurred: %s\n%s\n" % (
            str(error), 
            "".join(traceback.format_tb(sys.exc_info()[2]))))
        if params:
            print(params)    

