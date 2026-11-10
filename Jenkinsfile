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
                    # Run tests and output JUnit XML report for Jenkins UI
                    pytest test_app.py -v --junitxml=test-reports/results.xml
                    deactivate
                    rm -rf venv
                '''
            }
            post {
                always {
                    // Publishes test charts directly in the Jenkins job dashboard
                    junit allowEmptyResults: true, testResults: 'test-reports/*.xml'
                }
            }
        }

        stage('Build Docker Image') {
            steps {
                sh 'docker compose build flask-app'
            }
        }

        stage('Deploy to Live Stack (CD)') {
            steps {
                //-p used so that it reuses the same project instead of creating a new one
                sh 'docker compose -p flask-monitoring-cicd up -d --no-deps flask-app'
            }
        }

        stage('Post-Deploy Health & Smoke Check') {
            steps {
                sh '''
                    sleep 3
                    # 1. Verify health & metrics endpoints
                    curl --fail http://localhost:5000/health
                    curl --fail http://localhost:5000/metrics

                    # 2. Verify live weather endpoint
                    curl --fail "http://localhost:5000/weather?city=London"

                    # 3. Verify error code handling (expected 400 & 500)
                    [ $(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/weather) -eq 400 ]
                    [ $(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/error) -eq 500 ]
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
        always {
            // Clean up test reports directory workspace
            sh 'rm -rf test-reports'
        }
    }
}
