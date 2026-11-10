pipeline {
    agent any

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Lint & Unit Tests') {
            steps {
                sh '''
                    python3 -m venv venv
                    . venv/bin/activate
                    pip install --quiet -r requirements.txt
                    pytest test_app.py -v
                '''
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker compose build flask-app'
            }
        }

        stage('Deploy to Live Stack (CD)') {
            steps {
                sh 'docker compose up -d --no-deps flask-app'
            }
        }

        stage('Post-Deploy Health Check') {
            steps {
                sh '''
                    sleep 3
                    curl --fail http://localhost:5000/health
                    curl --fail "http://localhost:5000/weather?city=London"
                    curl --fail http://localhost:5000/metrics
                '''
            }
        }

        stage('Generate Initial Traffic') {
            steps {
                sh 'bash traffic-burst.sh || true'
            }
        }
    }

    post {
        success {
            echo "✅ Deployment successful! Microservice is healthy and monitored on Grafana (http://localhost:3000)."
        }
        failure {
            echo "❌ Pipeline failed! Check logs or roll back."
        }
    }
}
