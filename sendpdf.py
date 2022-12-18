# Importing sendpdf function
# From pdf_mail Library

from pdf_mail import sendpdf
import os

def verzend_email(user):

	sender_email_address = os.environ['SENDER_EMAIL_ADDRESS']
	sender_email_password = os.environ['SENDER_EMAIL_PASSWORD']

	receiver_email_address = user.email

	# ex-"Heading of email"
	subject_of_email = "Actueel boodschappenlijstje"

	# ex-" Matter to be sent"
	body_of_email = f"Beste { user.fullname },\n\nIn de bijlage het actuele boodschappenlijstje.\n\nMet vriendelijke groet, \n\nde boodschappenman"

	# ex-"Name of file"
	filename = f"boodschappen-{ user.idi }"

	location_of_file = "./"


	# Create an object of sendpdf function
	k = sendpdf(sender_email_address,
				receiver_email_address,
				sender_email_password,
				subject_of_email,
				body_of_email,
				filename,
				location_of_file)

	# sending an email
	k.email_send()

