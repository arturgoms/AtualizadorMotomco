from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os 
import shutil
import pyDes
import sys
import datetime
from werkzeug import secure_filename
import boto3
import requests
import urllib

UPLOAD_FOLDER = '/upload'
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER 
 
@app.route("/", methods=['GET', 'POST'])
def index():
		return render_template("index.html")
 

@app.route('/calibracao', methods = ['GET', 'POST'])
def calibracao():
	if request.method == 'POST':
		if request.form['nserie']:
			nserie = request.form['nserie']
			print nserie
			calibracao(nserie)
			return render_template("index.html", status='Calibracao enviada (nserie)!')
		if request.files['cali']:
			f = request.files['cali']
			f.save(secure_filename(f.filename))
			shutil.move(f.filename, "upload/%s.txt" % f.filename[:-4])
			nserie = f.filename[:-4]
			file = open('upload/%s.txt' % nserie, "r")
			b64 = file.read()
			print "Downloading"
			tabela = decryptDES(b64)
			file.close()
			file1 = open('upload/%s.txt' % nserie, "w")
			file1.write(tabela) 
			file1.close()
			print "OK"
			a = ((tabela.split('\n'))[0].split(';'))
			print tabela
			os.rename('upload/%s.txt' % nserie, 'upload/%s.txt' % a[len(a)-2])
			s3 = boto3.client('s3')
			s3.upload_file('upload/%s.txt' % a[len(a)-2] , 'calibracao', '%s.txt' % a[len(a)-2], ExtraArgs={'ACL':'public-read'})
			os.remove("upload/%s.txt" % a[len(a)-2])
			return render_template("index.html", status='Calibracao enviada (arquivo)!')
		else:
			return render_template("index.html")

	else:
		return render_template("index.html")

@app.route('/curva', methods = ['GET', 'POST'])
def curva():
	if request.method == 'POST':
		if request.form['sha1']:
			return render_template("index.html", statusC='sha1')
		if request.files['curvas']:
			f = request.files['curvas']
			f.save(secure_filename(f.filename))
			return render_template("index.html", statusC='file')
	else:
		return render_template("index.html")


def auth():
	gauth = GoogleAuth()
	gauth.LoadCredentialsFile("credencials.txt")
	if gauth.credentials is None:
	    gauth.LocalWebserverAuth()
	elif gauth.access_token_expired:
	    gauth.Refresh()
	else:
	    gauth.Authorize()
	# Save the current credentials to a file
	gauth.SaveCredentialsFile("credencials.txt")
	drive = GoogleDrive(gauth)
	return drive

def compare(service):
	curvas = []
	""" Listando curvas """
	file_list = service.ListFile({'q': "'0B5gsyjY70lJ2UFRELW1FSTR5XzQ' in parents"}).GetList()
	for file1 in file_list:
	  	curvas.append('%s,%s,%s' % (file1['title'], file1['id'], file1['createdDate']))
	  	#print('title: %s, id: %s, date: %s' % (file1['title'], file1['id'], file1['createdDate']))
	  	"""Downloading curvas"""
	for i in range(0, len(curvas)):
		title, id, date= curvas[i].split(',')
		print curvas[i]
		arquivos = service.ListFile({'q': "'%s' in parents" % id}).GetList() 
		for curva in arquivos:
			print('title: %s, id: %s' % (curva['title'], curva['id']))

			curvaAssinada = service.CreateFile({'id': curva['id']}) 	
			path = "%s/%s" % (title,curva['title'])
			print path
			if not os.path.exists(path):
				try:
					os.makedirs(title)	

				except:
					print "Pasta ja existe"
				#print curvaAssinada['title']  # world.png
				curvaAssinada.GetContentFile(curvaAssinada['title'])
				#print title
			
				source = "%s" % (curvaAssinada['title'])
				destination = "%s/%s" % (title,curvaAssinada['title'])
				shutil.move(source, destination)

		assinatura = open("%s/assinatura.txt" % title, "r")
		lines =  assinatura.readlines()
		os.rename("%s/curva.txt" % title, "%s/%s.txt" % (title, lines[1].strip("\r\n")))
		shutil.copy("%s/%s.txt" % (title, lines[1].strip("\r\n")), "%s/" % ("upload"))
		file2 = open("curvasDrive.txt","a") 
		file2.write("%s.txt\n" % lines[1].strip("\r\n"))
	
def aws():
	import boto3
	# Let's use Amazon S3
	s3 = boto3.resource('s3')
	balde = your_bucket = s3.Bucket('curvas')
	'''for bucket in s3.buckets.all():
		print(bucket.name)'''
	file2 = open("curvasAws.txt","a")
	for s3_file in balde.objects.all():
		file2.write("%s\n" % s3_file.key)

def updateFiles(service):
	import boto3

	file_list = service.ListFile({'q': "'0B5gsyjY70lJ2UFRELW1FSTR5XzQ' in parents"}).GetList()
	for file1 in file_list:
	  	if not os.path.exists(file1['title']):
	  		compare(service)
			
		else:
			print "Curvas atualizadas"
			aws()
			break
	fileDrive = open("curvasDrive.txt", "r")
	linesDrive =  fileDrive.readlines()
	fileAws = open("curvasAws.txt", "r")
	linesAws =  fileAws.readlines()
	CurvasUpload = []
	for i in range (0 , len(linesDrive)):
		if linesDrive[i] != linesAws[len(linesAws)-1]:
			CurvasUpload.append(linesDrive[i].strip("\r\n"))
		else:
			break
	print CurvasUpload
	s3 = boto3.client('s3')
	bucket_name = 'curvas'
	for i in range(0, len(CurvasUpload)):
		filename = CurvasUpload[i]
		s3.upload_file("upload/%s" % filename, bucket_name, filename, ExtraArgs={'ACL':'public-read'})
	print "OK"


def calculate_crc(tamanho, data):
    crc_register = np.uint16(0)
    polynom = np.uint16(0x8005)
    crc = []
    for i in range(0, tamanho):
        shift_register = np.uint8(0x01)
        while shift_register < 129:
            data_bit = np.uint8(1 if (np.bitwise_and(np.uint8(bytearray(data[i])), np.uint8(shift_register))) else 0)
            crc_bit = np.uint8(crc_register >> 15)
            crc_register = np.uint16(np.left_shift(np.uint16(crc_register), 1))
            shift_register = shift_register << 1
            if (np.bitwise_xor(data_bit, crc_bit)) != 0:
                crc_register = np.uint16(np.bitwise_xor(crc_register, polynom))

    crc.insert(0, np.bitwise_and(crc_register, 0x00FF))
    crc.insert(1, (crc_register >> 8))

    return crc

def decryptDES(data):
	

	import pyDes
	import base64
	a = bytearray([128, 193, 99, 197, 120, 102, 163, 123, 207, 236, 87, 166, 114, 130, 102, 166, 70,113, 48, 195, 0, 0, 0, 0])
	b = bytearray([218, 57, 163, 238, 94, 107, 75, 13])
	k = pyDes.triple_des(str(a), pyDes.CBC, str(b), pad=None, padmode=pyDes.PAD_PKCS5)
	f = (k.decrypt(data.decode('base64')))
	#print "Decrypted: %r" % str(f).replace('\x00','')
	return str(f).replace('\x00','')

def calibracao(nserie):
	#nserie = raw_input("Insira o numero de serie: ")
	url = "https://www.motomco.com.br/erp_pt/include/vendas/download.php?arquivo=../../../cript/%s.Clb" % nserie
	urllib.urlretrieve(url, 'calibracao/%s.txt' % nserie)
	print url
	file = open('calibracao/%s.txt' % nserie, "r")
	b64 = file.read()
	print "Downloading"
	tabela = decryptDES(b64)
	file.close()
	file1 = open('calibracao/%s.txt' % nserie, "w")
	file1.write(tabela) 
	file1.close()
	print "OK"
	a = ((tabela.split('\n'))[0].split(';'))
	print tabela
	os.rename('calibracao/%s.txt' % nserie, 'calibracao/%s.txt' % a[len(a)-2])
	s3 = boto3.client('s3')
	s3.upload_file('calibracao/%s.txt' % a[len(a)-2] , 'calibracao', '%s.txt' % a[len(a)-2], ExtraArgs={'ACL':'public-read'})


if __name__ == '__main__':
  app.run()