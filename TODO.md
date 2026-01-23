Product: 
- write better analysis prompt: figure out what to extract
- add some sort of memory: either pass in previous state, or what

Viewer:
- add save button for t he prompt
- deploy it on a server
- make it run with images uploaded to FTP server
- fix sessions, seems like everytime we take a snapshot in the viewer we get a new session
- add button to remove sessison to poubelle

GTM:
- improve the Viz

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