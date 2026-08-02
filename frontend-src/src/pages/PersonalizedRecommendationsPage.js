import React, { useState } from 'react';
import { 
  Card, 
  Button, 
  Upload, 
  message, 
  Typography, 
  Space, 
  Row, 
  Col, 
  Spin,
  Alert,
  Input,
  Switch,
  Tooltip,
  Divider
} from 'antd';
import { 
  UploadOutlined, 
  StarOutlined, 
  InfoCircleOutlined,
  BulbOutlined
} from '@ant-design/icons';
import { useQuery } from 'react-query';
import { getPersonalizedRecommendations, getRerankingExplanation } from '../services/api';
import RerankingScore from '../components/RerankingScore';

const { Title, Paragraph, Text } = Typography;
const { TextArea } = Input;

const PersonalizedRecommendationsPage = () => {
  const [resumeFile, setResumeFile] = useState(null);
  const [userDescription, setUserDescription] = useState('');
  const [showExplanations, setShowExplanations] = useState(true);
  const [limit, setLimit] = useState(10);

  const { data: recommendations, isLoading, error, refetch } = useQuery(
    ['personalizedRecommendations', resumeFile, userDescription, showExplanations, limit],
    () => getPersonalizedRecommendations(
      resumeFile, 
      userDescription || undefined, 
      limit, 
      showExplanations
    ),
    {
      enabled: false, // Only run when manually triggered
      retry: 1
    }
  );

  const handleResumeUpload = (file) => {
    const isPdf = file.type === 'application/pdf';
    const isDoc = file.type === 'application/msword' || file.type === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    
    if (!isPdf && !isDoc) {
      message.error('You can only upload PDF or DOC files!');
      return false;
    }
    
    const isLt10M = file.size / 1024 / 1024 < 10;
    if (!isLt10M) {
      message.error('File must be smaller than 10MB!');
      return false;
    }
    
    setResumeFile(file);
    message.success('Resume uploaded successfully!');
    return false; // Prevent auto upload
  };

  const handleGetRecommendations = () => {
    if (!resumeFile) {
      message.warning('Please upload your resume first');
      return;
    }
    refetch();
  };

  const formatSalary = (salary) => {
    if (!salary) return 'Not specified';
    const minSalary = Number(salary.min_salary) || 0;
    const maxSalary = Number(salary.max_salary) || 0;
    if (minSalary <= 0 && maxSalary <= 0) return 'Not specified';
    if (minSalary > 0 && maxSalary > 0) {
      return `$${minSalary.toLocaleString()} - $${maxSalary.toLocaleString()}`;
    }
    if (minSalary > 0) {
      return `$${minSalary.toLocaleString()}+`;
    }
    if (maxSalary > 0) {
      return `Up to $${maxSalary.toLocaleString()}`;
    }
    return 'Not specified';
  };

  const handleGetExplanation = async (jobId) => {
    try {
      // Call API with the current resume and user description for personalized explanation
      const explanation = await getRerankingExplanation(
        jobId, 
        userDescription || null, 
        resumeFile
      );
      return explanation;
    } catch (error) {
      console.error('Failed to get explanation:', error);
      message.error('Failed to get job explanation');
      return null;
    }
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <Title level={2} style={{ textAlign: 'center', marginBottom: '32px' }}>
        🎯 Personalized Job Recommendations
      </Title>

      <Paragraph style={{ textAlign: 'center', fontSize: '16px', marginBottom: '32px' }}>
        Upload your resume and get AI-powered job recommendations tailored to your skills, 
        experience, and preferences.
      </Paragraph>

      {/* Upload Section */}
      <Card style={{ marginBottom: '24px' }}>
        <Title level={4}>
          <UploadOutlined /> Upload Your Resume
        </Title>
        <Row gutter={[24, 24]}>
          <Col xs={24} md={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Upload
                beforeUpload={handleResumeUpload}
                showUploadList={false}
                accept=".pdf,.doc,.docx"
              >
                <Button
                  icon={<UploadOutlined />}
                  size="large"
                  type={resumeFile ? 'primary' : 'default'}
                  style={{ width: '100%', height: '60px' }}
                >
                  {resumeFile ? 'Resume Uploaded ✓' : 'Choose Resume File'}
                </Button>
              </Upload>
              <Text type="secondary">
                Supported formats: PDF, DOC, DOCX (max 10MB)
              </Text>
            </Space>
          </Col>
          <Col xs={24} md={12}>
            <Space direction="vertical" style={{ width: '100%' }}>
              <Text strong>Additional Preferences (Optional)</Text>
              <TextArea
                placeholder="Describe your ideal job, career goals, or specific requirements..."
                value={userDescription}
                onChange={(e) => setUserDescription(e.target.value)}
                rows={4}
              />
            </Space>
          </Col>
        </Row>
      </Card>

      {/* Options */}
      <Card style={{ marginBottom: '24px' }}>
        <Title level={4}>
          <StarOutlined /> Recommendation Options
        </Title>
        <Row gutter={[24, 16]}>
          <Col xs={24} sm={12} md={8}>
            <Space>
              <Switch 
                checked={showExplanations} 
                onChange={setShowExplanations}
                checkedChildren="On"
                unCheckedChildren="Off"
              />
              <Text>Show Explanations</Text>
              <Tooltip title="Show detailed explanations for why jobs are recommended">
                <InfoCircleOutlined style={{ color: '#1890ff' }} />
              </Tooltip>
            </Space>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Space>
              <Text strong>Number of Recommendations:</Text>
              <Input
                type="number"
                min={1}
                max={50}
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 10)}
                style={{ width: 80 }}
              />
            </Space>
          </Col>
          <Col xs={24} sm={12} md={8}>
            <Button
              type="primary"
              size="large"
              icon={<BulbOutlined />}
              onClick={handleGetRecommendations}
              loading={isLoading}
              disabled={!resumeFile}
              style={{ width: '100%' }}
            >
              Get Recommendations
            </Button>
          </Col>
        </Row>
      </Card>

      {/* Loading */}
      {isLoading && (
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <Spin size="large" />
          <div style={{ marginTop: '16px' }}>
            <Text>Analyzing your resume and finding the best matches...</Text>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <Alert
          message="Error Getting Recommendations"
          description="There was an error processing your resume. Please try again."
          type="error"
          showIcon
        />
      )}

      {/* Results */}
      {recommendations && (
        <Card>
          <div style={{ marginBottom: '24px' }}>
            <Title level={4} style={{ margin: 0 }}>
              🎯 Your Personalized Recommendations
            </Title>
            <div style={{ marginTop: '8px' }}>
              <Text>
                {recommendations.total_count} jobs found
                {recommendations.search_time_ms && (
                  <span style={{ marginLeft: '16px', color: '#666' }}>
                    (Search took {recommendations.search_time_ms.toFixed(0)}ms)
                  </span>
                )}
                {recommendations.reranking_time_ms && (
                  <span style={{ marginLeft: '16px', color: '#1890ff' }}>
                    (Reranking took {recommendations.reranking_time_ms.toFixed(0)}ms)
                  </span>
                )}
              </Text>
            </div>
          </div>

          {/* Reranking Statistics */}
          {recommendations.reranking_statistics && (
            <Card size="small" style={{ marginBottom: 24, backgroundColor: '#f6ffed' }}>
              <Row gutter={16}>
                <Col span={6}>
                  <Text strong>Average Match Score:</Text>
                  <br />
                  <Text style={{ color: '#52c41a', fontSize: '16px' }}>
                    {(recommendations.reranking_statistics.average_score * 100).toFixed(1)}%
                  </Text>
                </Col>
                <Col span={6}>
                  <Text strong>High Quality Matches:</Text>
                  <br />
                  <Text style={{ color: '#52c41a', fontSize: '16px' }}>
                    {recommendations.reranking_statistics.high_quality_matches}
                  </Text>
                </Col>
                <Col span={6}>
                  <Text strong>Medium Quality Matches:</Text>
                  <br />
                  <Text style={{ color: '#1890ff', fontSize: '16px' }}>
                    {recommendations.reranking_statistics.medium_quality_matches}
                  </Text>
                </Col>
                <Col span={6}>
                  <Text strong>Low Quality Matches:</Text>
                  <br />
                  <Text style={{ color: '#faad14', fontSize: '16px' }}>
                    {recommendations.reranking_statistics.low_quality_matches}
                  </Text>
                </Col>
              </Row>
            </Card>
          )}

          {recommendations.jobs.length === 0 ? (
            <Alert
              message="No recommendations found"
              description="Try uploading a different resume or adjusting your preferences."
              type="info"
              showIcon
            />
          ) : (
            <div>
              {recommendations.jobs.map((job, index) => (
                <Card key={job.id} style={{ marginBottom: 16 }} hoverable>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                    <div>
                      <Title level={4} style={{ margin: 0, color: '#1890ff' }}>
                        #{index + 1} {job.title}
                      </Title>
                      <Text strong style={{ fontSize: '16px' }}>{job.company_name}</Text>
                      <br />
                      <Text type="secondary">
                        📍 {job.location.city}, {job.location.state}
                        {job.remote_allowed && <span style={{ marginLeft: '8px', color: '#1890ff' }}>• Remote</span>}
                        {job.visa_sponsorship && <span style={{ marginLeft: '8px', color: '#52c41a' }}>• H1B Sponsor</span>}
                      </Text>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <Text strong style={{ fontSize: '16px' }}>
                        {formatSalary(job.salary)}
                      </Text>
                    </div>
                  </div>
                  
                  {/* Reranking Score */}
                  {job.rerank_score !== undefined && (
                    <RerankingScore 
                      score={job.rerank_score}
                      showDetails={showExplanations}
                      jobId={job.id}
                      onGetExplanation={handleGetExplanation}
                    />
                  )}
                  
                  <Divider />
                  
                  <Paragraph ellipsis={{ rows: 3 }}>
                    {job.description}
                  </Paragraph>
                  
                  <div style={{ marginTop: 16 }}>
                    <Text strong>Required Skills:</Text>
                    <div style={{ marginTop: 8 }}>
                      {job.required_skills.slice(0, 8).map((skill) => (
                        <span
                          key={skill}
                          style={{
                            display: 'inline-block',
                            backgroundColor: '#f0f0f0',
                            padding: '4px 8px',
                            margin: '2px 4px 2px 0',
                            borderRadius: '4px',
                            fontSize: '12px'
                          }}
                        >
                          {skill}
                        </span>
                      ))}
                      {job.required_skills.length > 8 && (
                        <span style={{ color: '#666', fontSize: '12px' }}>
                          +{job.required_skills.length - 8} more
                        </span>
                      )}
                    </div>
                  </div>
                  
                  {job.preferred_skills.length > 0 && (
                    <div style={{ marginTop: 12 }}>
                      <Text strong>Preferred Skills:</Text>
                      <div style={{ marginTop: 8 }}>
                        {job.preferred_skills.slice(0, 5).map((skill) => (
                          <span
                            key={skill}
                            style={{
                              display: 'inline-block',
                              backgroundColor: '#e6f7ff',
                              padding: '4px 8px',
                              margin: '2px 4px 2px 0',
                              borderRadius: '4px',
                              fontSize: '12px',
                              color: '#1890ff'
                            }}
                          >
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          )}
        </Card>
      )}
    </div>
  );
};

export default PersonalizedRecommendationsPage;
