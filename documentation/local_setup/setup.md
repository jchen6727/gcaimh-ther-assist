set default browser:
-> `Safari` for full projects
-> `Google Chrome` for limited projects

best option:
use `defaultbrowser`
https://formulae.brew.sh/formula/defaultbrowser

alternative:
options for opening with `--make-default-browser` through `Chrome` based browsers
`open -a "Google Chrome" --args --make-default-browser`
but it doesn't exist for `Safari`

also, cannot set the default user through CLI
`open -n -a "Google Chrome" --args --profile-directory="<PROFILE>"`
sets the profile for that session only

then:
`gcloud auth login` for full projects
`gcloud auth login --login-config="<JSON>"` for limited projects

can do:
`source ~/dev/gcaimh/local/set.zsh`
`gcloud auth login --login-config=$AUTH_JSON`

see projects:
`gcloud projects list`

then:
`gcloud config set project <PROJECT>` 
-> `brk-prj-salvador-dura-bern-sbx`
-> `732496392829` 

validate:
```
(dev) ➜  ~ gcloud config get-value project
732496392829
(dev) ➜  ~ gcloud projects describe 732496392829
createTime: '2023-09-25T18:55:02.016849Z'
lifecycleState: ACTIVE
name: Dura-Bernal-Lab
parent:
  id: '546510575975'
  type: organization
projectId: dura-bernal-lab
projectNumber: '732496392829'
```

for gcloud API
`gcloud auth application-default login` ( + `--login-config=$AUTH_JSON`)
`gcloud auth application-default set-quota-project $(gcloud config get-value project)`

for gcloud CLI (DON'T USE!)
`gcloud config set billing/quota_project $(gcloud config get-value project)`
### DON'T USE THIS! IT BREAKS GCLOUD CLI!
### KEEP IT AT DEFAULT "CURRENT_PROJECT"
`gcloud config get billing/quota_project`

after enabling services...
```
(dev) ➜  ~ gcloud services list --available --project=$(gcloud config get-value project) --filter="name:discoveryengine.googleapis.com"
NAME                            TITLE
discoveryengine.googleapis.com  Discovery Engine API
```