pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        stage('Install Dependencies & Test') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install -r requirements.txt
                    pytest test_app.py
                '''
            }
        }
        stage('Build Docker Image') {
            steps {
                sh 'docker build -t flask-monitoring-app:${BUILD_NUMBER} .'
            }
        }
    }
}
