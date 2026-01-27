#!/usr/bin/env zsh

conda activate gcaimh
echo "conda environment 'gcaimh' activated."

export PROJECT_ID="brk-prj-salvador-dura-bern-sbx"
export GOOGLE_CLOUD_PROJECT="brk-prj-salvador-dura-bern-sbx"
export GOOGLE_CLOUD_LOCATION="us-central1"
export GOOGLE_GENAI_USE_VERTEXAI="true"

echo "Environment variables have been set:"
echo "PROJECT_ID = \"$PROJECT_ID\""
echo "GOOGLE_CLOUD_PROJECT = \"$GOOGLE_CLOUD_PROJECT\""
echo "GOOGLE_CLOUD_LOCATION = \"$GOOGLE_CLOUD_LOCATION\""
echo "GOOGLE_GENAI_USE_VERTEXAI = \"$GOOGLE_GENAI_USE_VERTEXAI\""

export AUTH_JSON="/Users/jchen/dev/gcaimh/local/gcloud.json"
export UNSET_SCRIPT="/Users/jchen/dev/gcaimh/local/unset.zsh"

echo "\nUtility variables have been set:"
echo "AUTH_JSON = \"$AUTH_JSON\""
echo "UNSET_SCRIPT = \"$UNSET_SCRIPT\""

echo "\nPlease run the following commands manually to authenticate through your browser:"
echo "gcloud auth login --login-config=\$AUTH_JSON"
echo "gcloud auth application-default login --login-config=\$AUTH_JSON"

echo "\n# To unset the environment variables, run:"
echo "# source \$UNSET_SCRIPT"
