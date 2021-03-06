from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from elasticsearch import Elasticsearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
from credentials import aws_id, aws_key, consumer_key, consumer_secret, access_token, access_token_secret, es_host, arn
import json
import boto.sqs
from boto.sqs.message import Message
import ast
from django.views.decorators.csrf import csrf_exempt

from .forms import UploadFileForm
from .script import go
import StringIO
import zipfile
import os

shared = {}
count = 0
c=0
awsauth = AWS4Auth(aws_id, aws_key,'us-west-2','es')
es = Elasticsearch(
        hosts=[{'host': 'search-es-twitter-yarekxa5djp3rkj7kp735gvacy.us-west-2.es.amazonaws.com', 'port': 443}],
        use_ssl=True,
        http_auth=awsauth,
        verify_certs=True,
        connection_class=RequestsHttpConnection
        )
print(es.info())

def download_zip(request, fnames):
	filenames = fnames.split(',')
	zip_subdir = "files"
	zip_filename = "%s.zip" % zip_subdir

	# Open StringIO to grab in-memory ZIP contents
	s = StringIO.StringIO()

	# The zip compressor
	zf = zipfile.ZipFile(s, "w")

	for fpath in filenames:
		# Calculate path for file in zip
		fdir, fname = os.path.split(fpath)
		zip_path = os.path.join(zip_subdir, fname)

		# Add file, at correct path
		zf.write('polls/'+fpath, zip_path)

	# Must close zip for all contents to be written
	zf.close()

	# Grab ZIP file from in-memory, make response with correct MIME-type
	resp = HttpResponse(s.getvalue())
	resp['content_type'] = "application/x-zip-compressed"
	# ..and correct content-disposition
	resp['Content-Disposition'] = 'attachment; filename=%s' % zip_filename
	return resp


def download(request, file):
	with open('polls/'+file, 'rb') as pdf:
		response = HttpResponse(pdf.read())
		response['content_type'] = 'application/pdf'
		response['Content-Disposition'] = 'attachment;filename=file.docx'
		print('Returning file')
		return response

def submit(request):
	print('Here')
	if request.method == 'POST':
		form = UploadFileForm(request.POST, request.FILES)
		flist, fnames = handle_uploaded_file(request.FILES.get('word_file', None), request.FILES.get('data_file', None), request.POST['variable_names'])
		#return HttpResponseRedirect('polls/submit')
		return render(request, "polls/done.html", {'flist':flist, 'fnames':fnames})

	else:
		print('Here')
		form = UploadFileForm()
		return render(request, 'polls/word.html', {'form': form})

def handle_uploaded_file(f1, f2, vnames):
	print('In upload file')
	vnames = vnames.split(',')
	vnames = [t.strip() for t in vnames if t.strip!='']
	with open('polls/demo.docx', 'wb+') as destination:
		for chunk in f1.chunks():
			destination.write(chunk)
	with open('polls/data.csv', 'wb+') as destination:
		for chunk in f2.chunks():
			destination.write(chunk)
	flist = go(vnames)
	fnames = ''
	first = True
	for n in flist:
		if first:
			fnames = n
			first = False
		else:
			fnames += ',' + n
	return flist, fnames

class NotificationManager():
	def __init__(self, aws_id, aws_key, aws_region='us-west-2', sqs_name='new-tweet-notifs'):
		try:
			#connect with sqs
			self.aws_id = aws_id
			self.aws_key = aws_key
			self.sqs = boto.sqs.connect_to_region(aws_region, aws_access_key_id=aws_id, aws_secret_access_key=aws_key)
			self.sqs_queue = self.sqs.get_queue(sqs_name)
		except Exception as e:
			print('Could not connect to SQS')
			print(e)
		print('Connected to AWS SQS: '+ str(self.sqs))
		
	def openNotifications(self):
		#poll for new notifs every second
		rs = self.sqs_queue.get_messages() #result set
		print(len(rs))
		res = {}
		if len(rs) > 0:
			for m in rs:
				#print('Opening notification')
				body = m.get_body()
				tweet= ast.literal_eval(body)

				res[tweet['id']] = tweet

				#delete notification when done
				self.sqs_queue.delete_message(m)
				#print('Done')
		return res

def index(request):
    return render(request, "polls/word.html")

# @csrf_exempt
# def submit(request):
# 	print(request.POST)

@csrf_exempt
def testfun(request):
	print('\n\n')
	print(request.body)
	print('\n\n')
	from django.http import JsonResponse
	global shared
	global c
	c+=1
	shared[c] = ast.literal_eval(ast.literal_eval(request.body)['Message'])
	return JsonResponse({'hi':shared[c]})

def livestream(request):
	global count
	count += 1
	#print(count)
	"""
    ... do the processing you want as if it is a normal web request.
    ... like querying the database
    ... you can return a `json` dictionary 
    ... or a normal `render_to_response` template with html
    """
	#print('****\nFetching New Tweets\n****')
	#notman = NotificationManager(aws_id, aws_key)
	#poll sns

	from django.http import JsonResponse
	#return JsonResponse(notman.openNotifications())
	global shared
	print(shared)
	resp = shared
	shared = {}
	c=0
	return JsonResponse(resp)

def map(request):
	term = 'none'
	if request.method == 'POST':
		print('POST req')
		term = request.POST.get('select')
	filtered_query = {"query":{"match":{"text":term}}}
	no_filter_query = {"query":{"match_all":{}}}
	q = filtered_query
	if term == 'none':
		q = no_filter_query
	res = es.search(size=5000, index="tweets", doc_type="twitter_twp", body=q)
	coordinate_array = []
	coordinates = res['hits']
	individual_coordinate_sets = coordinates['hits']
	list_of_dicts = [dict() for num in range (len(individual_coordinate_sets))]
	for idx,element in enumerate(list_of_dicts):
		source_value = individual_coordinate_sets[idx]['_source']
		temp_coordinates = source_value['coordinates']['coordinates']
		#print(temp_coordinates)
		#tweet_info = source_value['user'] + ": " + source_value['content']
		list_of_dicts[idx] = dict(lng=temp_coordinates[0], lat = temp_coordinates[1], sentiment=str(source_value['sentiment']))#, sentiment=source_value['sentiment'])
	print(list_of_dicts)
	return render(request, "polls/maps.html", {'plot':list_of_dicts})