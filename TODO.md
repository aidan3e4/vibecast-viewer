Product: 
- write better analysis prompt: figure out what to extract
- add prompt versioning
- add some sort of memory: either pass in previous state, or what

Viewer / UI:
- add save button for the prompt
- fix sessions, seems like everytime we take a snapshot in the viewer we get a new session -- also sessions created through the UI should be downloaded locally here in my data folder
- there is a bug in make viewer -- check logs

Deployment:
- check reolink upload
    - to S3 by FTP
    - find if raspberry pi is needed to upload
- figure out how to decouple upload from processing. Can the orange pi do all the processing ? The LLM call is fine, the unwarping and all is probably not
- deploy a serverless function to process on runpod
- best practice to inject some vars into the script, for now they're copied from local repo

Engineer debt / optimizations:
- make LLM client async --> use vllm
- split vision_llm into a CV part and an LLM part
- upload the data with FTPS instead of FTP (more secure)


Simplify the way we connect the cam
- dockerize the FTP server
- deploy on runpod and test
- make it easy to setup the camera on a new wifi
- setup FTP to not be on disk, because we need it to be permanent