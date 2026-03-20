# Start from Linux with Python installed 
FROM python:3.11        
# Create working directory (inside container)
WORKDIR /app            
# copy project files into container
COPY . .    
# install dependencies            
RUN pip install -r requirements.txt   
# run the app
CMD ["python", "main.py"]              