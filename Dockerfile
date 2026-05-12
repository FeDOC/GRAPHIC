# Start from Linux with Python installed 
FROM python:3.11-slim
# Create working directory (inside container)
WORKDIR /app            
# copy project files into container
COPY requirements.txt .

RUN pip install -r requirements.txt  

COPY . .    

#install dependencies             
 
# run the app
CMD ["gunicorn", "-b", "0.0.0.0:5000", "main:app"]              