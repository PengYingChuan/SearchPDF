#from __future__ import print_function
import glob
import os
import re
import json

from pdfminer.pdfparser import PDFParser

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfdocument import PDFNoOutlines

from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter

from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed

from pdfminer.pdfdevice import PDFDevice

from pdfminer.converter import PDFPageAggregator

from pdfminer.layout import LAParams
from pdfminer.layout import LTTextBox
from pdfminer.layout import LTTextLine
from pdfminer.layout import LTFigure
from pdfminer.layout import LTImage
from flask import Flask, render_template, request, url_for
from sqlite3 import dbapi2 as sqlite3
from flask import session, g, redirect, abort, flash, _app_ctx_stack

import ntpath
import sys, getopt
import unicodedata
import pdfquery
import dropbox
import posixpath
from flask import redirect, abort

from dropbox.client import DropboxClient, DropboxOAuth2Flow
from pyPdf import PdfFileReader, PdfFileWriter

# configuration
DEBUG = True
DATABASE = 'myapp.db'
SECRET_KEY = 'development key'

# Fill these in!
DROPBOX_APP_KEY = '63d9tw3caqcv9i7' 
DROPBOX_APP_SECRET = 'zzs5wm0il5amm9z'

# create our little application :)
app = Flask(__name__)
app.config.from_object(__name__)
app.config.from_envvar('FLASKR_SETTINGS', silent=True)

# Ensure instance directory exists.
try:
    os.makedirs(app.instance_path)
except OSError:
    pass

def init_db():
    """Creates the database tables."""
    with app.app_context():
        db = get_db()
        with app.open_resource("schema.sql", mode="r") as f:
            db.cursor().executescript(f.read())
        db.commit()

def get_db():
    """
    Opens a new database connection if there is none yet for the current application context.
    """
    top = _app_ctx_stack.top
    if not hasattr(top, 'sqlite_db'):
        sqlite_db = sqlite3.connect(os.path.join(app.instance_path, app.config['DATABASE']))
        sqlite_db.row_factory = sqlite3.Row
        top.sqlite_db = sqlite_db

    return top.sqlite_db

def get_access_token():
    username = session.get('user')
    if username is None:
        return None
    db = get_db()
    row = db.execute('SELECT access_token FROM users WHERE username = ?', [username]).fetchone()
    if row is None:
        return None
    return row[0]

@app.route('/startDrop', methods=['GET'])
def startDrop():
    if 'user' not in session:
        return redirect(url_for('login'))
    access_token = get_access_token()
    
    real_name = None
    app.logger.info('access token = %r', access_token)
    if access_token is not None:
	print("Creating Client start drop")
        client = DropboxClient(access_token)
        account_info = client.account_info()
        real_name = account_info["display_name"]
    return render_template('index1.html')

@app.route('/dropbox-auth-finish')
def dropbox_auth_finish():
    username = session.get('user')
    print ("your here------------------------------------------------------------------------------------------------")
    
    print (username)
    print ("your here------------------------------------------------------------------------------------------------")
    access = session.get('access_token')
    print ("your here------------------------------------------------------------------------------------------------")
    print (access)
    
    print ("your here------------------------------------------------------------------------------------------------")
    
    if username is None:
        abort(403)
    try:
        access_token, user_id, url_state = get_auth_flow().finish(request.args)
    except DropboxOAuth2Flow.BadRequestException, e:
        abort(400)
    except DropboxOAuth2Flow.BadStateException, e:
        abort(400)
    except DropboxOAuth2Flow.CsrfException, e:
        abort(403)
    except DropboxOAuth2Flow.NotApprovedException, e:
        flash('Not approved?  Why not')
        return redirect(url_for('startDrop'))
    except DropboxOAuth2Flow.ProviderException, e:
        app.logger.exception("Auth error" + e)
        abort(403)
    db = get_db()
    print ("your here------------------------------------------------------------------------------------------------")
    print (access_token)
    print ("your here------------------------------------------------------------------------------------------------")
    data = [access_token, username]
    db.execute('UPDATE users SET access_token = ? WHERE username = ?', data)
    db.commit()
    print("Creating Client drop autho finish")
    client=dropbox.client.DropboxClient(access_token)
    dropbox_folders = list_folders_in_background("/", 1, client)
    print (dropbox_folders)
    #return redirect(url_for('form',  _external=True, _scheme='http'))
    return render_template('index.html', folder=dropbox_folders)

@app.route('/dropbox-auth-start')
def dropbox_auth_start():
    if 'user' not in session:
        return render_template('errorLink.html')
    return redirect(get_auth_flow().start())

@app.route('/dropbox-unlink')
def dropbox_unlink():
	username = session.get('user')
	if username is None:
		return redirect(url_for('dropbox_logout'))
	db = get_db()
	db.execute('UPDATE users SET access_token = NULL WHERE username = ?', [username])
	db.commit()
	return redirect(url_for('dropbox_logout'))

@app.route('/dropbox-logout')
def dropbox_logout():
    username = session.get('user')
    if username is None:
        return render_template('error.html')
    db = get_db()
    db.execute('UPDATE users SET access_token = NULL WHERE username = ?', [username])
    db.commit()
    return render_template('redirect.html')

def get_auth_flow():
    redirect_uri = url_for('dropbox_auth_finish', _external=True, _scheme='https')
    return DropboxOAuth2Flow(DROPBOX_APP_KEY, DROPBOX_APP_SECRET, redirect_uri,
                         session, 'dropbox-auth-csrf-token')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        if username:
            db = get_db()
            db.execute('INSERT OR IGNORE INTO users (username) VALUES (?)', [username])
            db.commit()
            session['user'] = username
            flash('You were logged in')
            return redirect(url_for('startDrop'))
        else:
            flash("You must provide a username")
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('You were logged out')
    return redirect(url_for('startDrop'))

#----------------------End Dropbox logics---------------------------

"""	Function to get list of all docs in root_path	"""
def get_list_of_pdfs_on_local(path):	
	try:
		pdf_list = []
	
		os.chdir(path)
	
		for new_file in glob.glob("*.pdf"):
			pdf_list.append(new_file)
	
		print (pdf_list)
		return pdf_list
	except:
		print ("Exception while get_list_of_pdfs_on_local")



def get_list_of_pdfs_on_dropbox(path, client):
	try:
		temp_pdf_list = list_children_in_folder(path, False, client)
		pdf_list = []
	
		for file_index in range(0, len(temp_pdf_list)):
			try:
				temp_dict = {"filename" : "",
							"file_link" : ""}
				filename = decode_string(temp_pdf_list[file_index])
				temp_dict["filename"] = filename
				file_path = path+filename
				sharelink_dict = get_sharelink_for_file_at_path(file_path, client)
				sharelink = decode_string(sharelink_dict["url"])
				temp_dict["file_link"] = sharelink
				pdf_list.append(temp_dict)
			except:
				print ("Exception for file %s"% Exception)
	
		return pdf_list
	except:
		print ("Exception while get_list_of_pdfs_on_dropbox")


def download_pdf_from_dropx(path, filelist, download_path, client):
	try:
		downloadFile(filelist, path, client)
	except:
		print ("Exception while download_pdf_from_dropx")


def search_pdf(path, pdf_info, search_string):
	try:
		result_dict = {}
		result_pages = []
		is_found = False
		file_ptr = open(path+pdf_info["filename"], 'rb')
	
		parser = PDFParser(file_ptr)
		document = PDFDocument(parser, "")
	
		if not document.is_extractable:
			raise PDFTextExtractionNotAllowed
		else:
			resource_manager = PDFResourceManager()
			laparams = LAParams()
			device = PDFPageAggregator(resource_manager, laparams=laparams)
			interpreter = PDFPageInterpreter(resource_manager, device)
		
			for i, page in enumerate(PDFPage.create_pages(document)):
				try:
					"""	interpret the page	"""
					interpreter.process_page(page)
			
					"""	get page layout	"""
					layout = device.get_result()
			
					"""	get page content	"""
					page_content = parse_lt_objs(layout, (i+1)).decode("utf-8")
					search_res = re.search(search_string.lower(), page_content.lower())
			
					if search_res is not None:
						if is_found == False:
							result_dict["pdf_name"] = pdf_info["filename"]
							result_dict["pdf_link"] = pdf_info["file_link"]
							result_dict["pdf_path"] = path
							is_found = True
				
						page_info = {"page_num": i+1,
									"page_link": ""}
						result_pages.append(page_info)
						result_dict["result_pages"] = result_pages
				except:
					print ("Exception while handling page %d in search_pdf"% (i+1))

			if is_found == True:
				result_dict["result_pages"] = result_pages
			
		file_ptr.close()
	
		if is_found == True:
			return result_dict
		else:
			return False
	except:
		print ("Exception while search_pdf")



"""	Function to extract text out of pdf file	"""
def search_pdf_parent_folder(path, pdf_list, search_string):
	
	try:
		result_list = []
	
		"""	iterate through each pdf and call search on each of them	"""
		for file_index in range(0, len(pdf_list)):
			try:
				print ("%s in process"% pdf_list[file_index])
				search_dict = search_pdf(path, pdf_list[file_index], search_string)
				if search_dict is not False:
					result_list.append(search_dict)
			except:
				print ("Exception while search_pdf_parent_folder")
		
		return result_list
	except:
		print ("Exception while search_pdf_parent_folder")


def to_bytestring (s, enc='utf-8'):
	"""Convert the given unicode string to a bytestring, using the standard encoding,
    unless it's already a bytestring"""
	if s:
		if isinstance(s, str):
			return s
		else:
			return s.encode(enc)


def update_page_text_hash (h, lt_obj, pct=0.2):
	"""Use the bbox x0,x1 values within pct% to produce lists of associated text within the hash"""

	x0 = lt_obj.bbox[0]
	x1 = lt_obj.bbox[2]

	key_found = False
	for k, v in h.items():
		hash_x0 = k[0]
		if x0 >= (hash_x0 * (1.0-pct)) and (hash_x0 * (1.0+pct)) >= x0:
			hash_x1 = k[1]
			if x1 >= (hash_x1 * (1.0-pct)) and (hash_x1 * (1.0+pct)) >= x1:
				# the text inside this LT* object was positioned at the same
				# width as a prior series of text, so it belongs together
				key_found = True
				v.append(to_bytestring(lt_obj.get_text()))
				h[k] = v
	if not key_found:
		# the text, based on width, is a new series,
		# so it gets its own series (entry in the hash)
		h[(x0,x1)] = [to_bytestring(lt_obj.get_text())]

	return h


def parse_lt_objs (lt_objs, page_number, text=[]):
	text_content = [] 
	
	page_text = {}
	
	for lt_obj in lt_objs:
		if isinstance(lt_obj, LTTextBox) or isinstance(lt_obj, LTTextLine):
			page_text = update_page_text_hash(page_text, lt_obj)
	
	for k, v in sorted([(key,value) for (key,value) in page_text.items()]):
		text_content.append(''.join(v))

	return '\n'.join(text_content)


def extract_result_pages(xFileNameOriginal, xFileNameOutput, xPageStart, xPageEnd):
	try:
		output = PdfFileWriter()
		pdfOne = PdfFileReader(file(xFileNameOriginal, "rb"))
	
		for i in range(xPageStart, xPageEnd+1):
			try:
				output.addPage(pdfOne.getPage(i))
				outputStream = file(xFileNameOutput, "wb")
				output.write(outputStream)
				outputStream.close()
			except:
				print ("Exception while extracting page %d"% i)
	except:
		print ("Exception while extract_result_pages")


def write_output(result):
	print ("/n/nHere in write_output%s/n/n"%result)	
	try:
		for file_index in range(0, len(result)):
			try:
				temp_dict = result[file_index]
				found_pages = temp_dict["result_pages"]
			
				for page in range(0, len(found_pages)):
					try:
						output_path = temp_dict["pdf_path"]+str(found_pages[page]["page_num"])+"_"+temp_dict["pdf_name"]
						extract_result_pages(temp_dict["pdf_path"]+temp_dict["pdf_name"], output_path, temp_dict["result_pages"][page]["page_num"]-1, temp_dict["result_pages"][page]["page_num"]-1)
					except:
						print ("Exception while writing %d page in %s file"% (page,temp_dict["pdf_name"]))
			except:
				print ("Exception while writing output for %s file"% temp_dict["pdf_name"])
	except:
		print ("Exception while extract_result_pages")



def delete_files(path):
	for the_file in os.listdir(path):
		file_path = os.path.join(path, the_file)
		try:
			os.unlink(file_path)
		except Exception, e:
			print ("Exception while delete_files %s"% e)

#-----------------------------------------Flask-----------------------------

@app.route('/')
def form():
    print ("Dropbox-----Your DropboxFolder--------> %s"%dropbox_folders)
    return render_template('index.html', folder=dropbox_folders)



# Define a route for the action of the form, for example '/hello/'
# We are also defining which type of requests this route is 
# accepting: POST requests in this case
@app.route('/hello/', methods=['POST'])
def hello():
    
    search_path=request.form['yourPath']
    search_content=""+request.form['yourContent']

    access_token = get_access_token()
    print(access_token)
    client=dropbox.client.DropboxClient(access_token)
    
    
    pdf_list = get_list_of_pdfs_on_dropbox(search_path, client)
    temp_search_path = "/app/static/Downloaded/"
    download_pdf_from_dropx(search_path, pdf_list, temp_search_path, client)
    
    result = search_pdf_parent_folder(temp_search_path, pdf_list, search_content)

    jsondata = json.dumps(result)
    data = json.loads(jsondata)
    
    
    final_result=write_output_in_background(result, search_path, search_content, temp_search_path, client)

    return render_template('form_action.html', data=final_result)


#------------------List dropbox folders (New implimentations)------------

def list_folders_in_background(path, level, client):
	print ("in list_folders_in_background")
	print (path)
	print (level)
	print (client)
	dropbox_folders = list_folders_under_path(path, level, client)
	dropbox_folders_json = json.dumps(dropbox_folders)
    	data = json.loads(dropbox_folders_json)
	print ("folder list on dropbox \n%s\n"% dropbox_folders_json)
	#print ("folder count on dropbox: %s"% get_count_of_folders(dropbox_folders))
	return data


def write_output_in_background(result, search_path, search_context_string, temp_search_path, client):
	print ("running on background thread")
	write_output(result)
	folder_create_response = create_result_folder_on_dropbox(search_path+search_context_string+"_search_result", client)
	result = create_output_files_on_dropbox(result, folder_create_response["path"], client)
	for result_dict in result:
		del result_dict["pdf_path"]
	print ("final output is %s"% result)
	delete_files(temp_search_path)
	return result

def get_sharelink_for_file_at_path(path, client):
	try:
		sharelink = client.share(path, short_url = False)
		return sharelink
	except:
		print ("Exception while get_sharelink_for_file_at_path")


#function that shows the content of a directory
def list_children_in_folder(path, isFolderSearch, client):
	item_list = []

	try:
		folder_metadata = client.metadata(path)
	except:
		print ('The Directory does not exist')
		sys.exit(-1)
	
	if folder_metadata['is_dir'] == "False":
		print ('This is not a Directory')
		sys.exit(1)

	for I in folder_metadata['contents']:
		if isFolderSearch:
			if I['is_dir'] == True:
				ntpath.basename(I['path'])
				head, tail = ntpath.split(I['path'])
				folder_info = { "folder_name" : decode_string(tail),
								"folder_path" : decode_string(I["path"])
							}
				item_list.append(folder_info)
		else:
			ntpath.basename(I['path'])
			head, tail = ntpath.split(I['path'])
			if I['is_dir'] == False:
				if tail.endswith('.pdf'):
					item_list.append(tail)

	return item_list



#-----------------Dropbox fetching method---------------


#function that shows the content of a directory
def list_files(path, client):
	pdf_list = []

	try:
		folder_metadata = client.metadata(path)
	except:
		print ('The Directory does not exist')
		sys.exit(-1)

	print (folder_metadata['is_dir'])
	if folder_metadata['is_dir'] == "False":
		print ('This is not a Directory')
 		sys.exit(1)

	for I in folder_metadata['contents']:
		ntpath.basename(I['path'])
		head, tail = ntpath.split(I['path'])

		if I['is_dir'] == True:
			item_type = 'Dir'
		else:
			item_type = 'File'
			if tail.endswith(".pdf"):
 				pdf_list.append(tail)

	return pdf_list


# Function to Download a list of files
def downloadFile (filelist, path, client):
	for remoteFile in filelist:
		try:
			with client.get_file(path+'/'+remoteFile["filename"]) as f:
				download_path = "/app/static/Downloaded/"+remoteFile["filename"]
				new_file = open(download_path,'w')
				new_file.write(f.read())
				new_file.close()
		except:
			print ('An Error occcurs when try do download the Remote File'+Exception)


def create_result_folder_on_dropbox(path, client):
	try:
		return client.file_create_folder(path)
	except:
		folder_dict = {"path":path}
		print ("folder already exist returning %s"% folder_dict)
		return folder_dict


def create_output_files_on_dropbox(result, to_path, client):
	
	for search_res in result:
		for page in search_res["result_pages"]:
			try:
				local_file_path = search_res['pdf_path']+str(page["page_num"])+"_"+search_res["pdf_name"]
				fd = open(local_file_path, 'rb')
				file_create_response = client.put_file(to_path+'/'+str(page["page_num"])+"_"+search_res["pdf_name"], fd, overwrite = True)
				file_path_on_dropbox = decode_string(file_create_response["path"])
				sharelink_response = get_sharelink_for_file_at_path(file_path_on_dropbox, client)
				sharelink = decode_string(sharelink_response["url"])
				page["page_link"] = sharelink
				os.unlink(local_file_path)
			except:
				print ("Exception while create_output_files_on_dropbox %s"% Exception)
	return result


def decode_string(encoded_string):
	decoded_string = unicodedata.normalize('NFKD', encoded_string).encode('ascii','ignore')
	return decoded_string

def list_folders_under_path(path, level, client):
	
	try:
		folder_metadata = client.metadata(path)
		ntpath.basename(folder_metadata['path'])
		folder_path = decode_string(folder_metadata['path'])
		
		folder_children = {"path": folder_path,
						"level" : str(level),
					"subfolders": []
					}
		
		for db_item in folder_metadata['contents']:
			if db_item['is_dir'] == True:
				folder_children["subfolders"].append(list_folders_under_path(decode_string(db_item["path"])+"/", level+1, client))
		
		return folder_children

	except:
		print ('The Directory does not exist')



def get_count_of_folders(folder_children):
	try:
		count = 1
	
		subfolders = folder_children["subfolders"]
		for i in range(0, (len(subfolders))):
			count += get_count_of_folders(subfolders[i])
		
		return count
	except:
		print ("Exception while get_count_of_folders")



#--------------------End-----------------------------------------------------------------------------------

result = []
is_search_dropbox = True
dropbox_folders = {}

# Run the app :)
port = os.getenv('VCAP_APP_PORT', '5000')
if __name__ == '__main__':
	init_db()
	app.run(
		host='0.0.0.0', 
		port=int(port))
  #app.run( 
   #     host="0.0.0.0",
    #    port=int("80")
  #)