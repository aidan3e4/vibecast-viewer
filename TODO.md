FRIST:
- make it work. Some sort of app where we can see the images in S3, both raw fisheyed and unwrapped, and also directly see the results or even have a UI where we can call the backend to get new results

SECOND:
- make it work locally, then dockerize
- then deploy somewhere at a fixed address



Viewer / UI:
- add save button for the prompt
- fix sessions, seems like everytime we take a snapshot in the viewer we get a new session -- also sessions created through the UI should be downloaded locally here in my data folder
- there is a bug in make viewer -- check logs
