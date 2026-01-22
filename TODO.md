Tonight:
- check reolink upload
    - by http at link -- http://192.168.1.33/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=s&user=dan&password=dan11111
    - to S3 by FTP
- find if raspberry pi is needed to upload

Later:
- make the python script for image analysis run serverless in runpod

Product: 
- write better analysis prompt: figure out what to extract
- add some sort of memory: either pass in previous state, or what

GTM:
- improve the Viz

Deployment:
- figure out how to decouple the camera from the server that processes the image: need orange pi or something running next to it but not my computer. The orange pi has to take the stream and send it further to the server which does the processing. 
    - Can the orange pi do all the processing ? The LLM call is fine, the unwarping and all might not be
    - Maybe there is a server up that does the processing, and the orange pi just sends the images to it every few seconds or so
    - try http://[camera-ip-address]/cgi-bin/api.cgi?cmd=Snap&channel=0&rs=anyrandomstring&user=[your-username]&password=[your-password] to see if we get a snapshot from there
- deploy a serverless function to process. Use vLLM to try it
- best practice to inject some vars into the script, such as interval capture time, camera_ip, etc

Engineer debt / optimizations:
- make LLM client async --> use vllm
- split vision_llm into a CV part and an LLM part