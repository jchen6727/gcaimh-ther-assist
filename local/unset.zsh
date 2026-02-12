#!/usr/bin/env zsh

unset PROJECT_ID GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION GOOGLE_GENAI_USE_VERTEXAI

echo "Environment variables {PROJECT_ID GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION GOOGLE_GENAI_USE_VERTEXAI} have been unset..."

unset AUTH_JSON UNSET_SCRIPT

echo "Utility variables {AUTH_JSON UNSET_SCRIPT} have been unset..."

conda activate dev

echo "conda environment 'dev' activated."