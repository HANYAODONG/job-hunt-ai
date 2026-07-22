import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  Card, 
  Typography, 
  Tag, 
  Space, 
  Button, 
  Row, 
  Col, 
  Divider,
  Spin,
  Alert,
  List,
  message
} from 'antd';
import { 
  ArrowLeftOutlined, 
  EnvironmentOutlined, 
  DollarOutlined,
  CalendarOutlined,
  CheckCircleOutlined,
  StarOutlined
} from '@ant-design/icons';
import { useQuery } from 'react-query';
import { getJobById, getSimilarJobs } from '../services/api';
import JobApplicationModal from '../components/JobApplicationModal';
import { useAuth } from '../contexts/AuthContext';

const { Title, Paragraph, Text } = Typography;

const JobDetailsPage = () => {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [applicationModalVisible, setApplicationModalVisible] = useState(false);
  const { isAuthenticated } = useAuth();

  const { data: job, isLoading, error } = useQuery(
    ['job', jobId],
    () => getJobById(jobId),
    {
      enabled: !!jobId,
      retry: 1
    }
  );

  const { data: similarJobs } = useQuery(
    ['similarJobs', jobId],
    () => getSimilarJobs(jobId, 5),
    {
      enabled: !!jobId,
      retry: 1
    }
  );

  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '400px' 
      }}>
        <Spin size="large" />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
        <Alert
          message="Job Not Found"
          description="The job you're looking for doesn't exist or has been removed."
          type="error"
          showIcon
          action={
            <Button onClick={() => navigate('/search')}>
              Back to Search
            </Button>
          }
        />
      </div>
    );
  }

  if (!job) {
    return null;
  }

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

  const formatDate = (dateString) => {
    if (!dateString) return 'Not specified';
    return new Date(dateString).toLocaleDateString();
  };

  const handleApplyToJob = () => {
    if (!isAuthenticated()) {
      message.warning('Please login to apply for jobs');
      return;
    }
    setApplicationModalVisible(true);
  };

  const handleApplicationSubmitted = () => {
    message.success('Application submitted successfully!');
  };

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px' }}>
      <Button 
        icon={<ArrowLeftOutlined />} 
        onClick={() => navigate('/search')}
        style={{ marginBottom: '24px' }}
      >
        Back to Search
      </Button>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card>
            <div style={{ marginBottom: '24px' }}>
              <Title level={1} style={{ marginBottom: '8px' }}>
                {job.title}
              </Title>
              <Title level={3} style={{ color: '#1890ff', marginBottom: '16px' }}>
                {job.company_name}
              </Title>
              
              <Space wrap size="large">
                <Space>
                  <EnvironmentOutlined />
                  <Text>{job.location.city}, {job.location.state}</Text>
                  {job.remote_allowed && <Tag color="blue">Remote</Tag>}
                </Space>
                
                <Space>
                  <DollarOutlined />
                  <Text strong>{formatSalary(job.salary)}</Text>
                </Space>
                
                <Space>
                  <CalendarOutlined />
                  <Text>Posted: {formatDate(job.posted_date)}</Text>
                </Space>
                
                {job.visa_sponsorship && (
                  <Tag color="green" icon={<CheckCircleOutlined />}>
                    H1B Sponsorship Available
                  </Tag>
                )}
              </Space>
            </div>

            <Divider />

            <div style={{ marginBottom: '24px' }}>
              <Title level={3}>Job Description</Title>
              <Paragraph style={{ fontSize: '16px', lineHeight: '1.8' }}>
                {job.description}
              </Paragraph>
            </div>

            {job.responsibilities && job.responsibilities.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <Title level={3}>Responsibilities</Title>
                <List
                  dataSource={job.responsibilities}
                  renderItem={(item) => (
                    <List.Item>
                      <Text>• {item}</Text>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {job.requirements && job.requirements.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <Title level={3}>Requirements</Title>
                <List
                  dataSource={job.requirements}
                  renderItem={(item) => (
                    <List.Item>
                      <Text>• {item}</Text>
                    </List.Item>
                  )}
                />
              </div>
            )}

            <div style={{ marginBottom: '24px' }}>
              <Title level={3}>Required Skills</Title>
              <Space wrap>
                {job.required_skills.map((skill) => (
                  <Tag key={skill} color="red" style={{ fontSize: '14px', padding: '4px 12px' }}>
                    {skill}
                  </Tag>
                ))}
              </Space>
            </div>

            {job.preferred_skills && job.preferred_skills.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <Title level={3}>Preferred Skills</Title>
                <Space wrap>
                  {job.preferred_skills.map((skill) => (
                    <Tag key={skill} color="blue" style={{ fontSize: '14px', padding: '4px 12px' }}>
                      {skill}
                    </Tag>
                  ))}
                </Space>
              </div>
            )}

            {job.benefits && job.benefits.length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <Title level={3}>Benefits</Title>
                <List
                  dataSource={job.benefits}
                  renderItem={(benefit) => (
                    <List.Item>
                      <Space>
                        <CheckCircleOutlined style={{ color: '#52c41a' }} />
                        <Text strong>{benefit.name}</Text>
                        {benefit.description && <Text type="secondary">- {benefit.description}</Text>}
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            )}

            <div style={{ textAlign: 'center', marginTop: '32px' }}>
              <Space size="large">
                <Button type="primary" size="large" icon={<StarOutlined />}>
                  Save Job
                </Button>
                <Button 
                  type="primary" 
                  size="large"
                  onClick={handleApplyToJob}
                  style={{ 
                    background: 'linear-gradient(45deg, #52c41a, #1890ff)',
                    border: 'none',
                    fontWeight: 'bold'
                  }}
                >
                  Apply Now
                </Button>
              </Space>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Card title="Job Details" style={{ marginBottom: '24px' }}>
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <div>
                <Text strong>Job Type:</Text>
                <br />
                <Tag color="blue">{job.job_type?.replace('_', ' ').toUpperCase()}</Tag>
              </div>
              
              <div>
                <Text strong>Experience Level:</Text>
                <br />
                <Tag color="green">{job.experience_level?.replace('_', ' ').toUpperCase()}</Tag>
              </div>
              
              <div>
                <Text strong>Location:</Text>
                <br />
                <Text>{job.location.city}, {job.location.state}, {job.location.country}</Text>
              </div>
              
              <div>
                <Text strong>Salary Range:</Text>
                <br />
                <Text>{formatSalary(job.salary)}</Text>
              </div>
              
              <div>
                <Text strong>Posted Date:</Text>
                <br />
                <Text>{formatDate(job.posted_date)}</Text>
              </div>
              
              {job.application_deadline && (
                <div>
                  <Text strong>Application Deadline:</Text>
                  <br />
                  <Text>{formatDate(job.application_deadline)}</Text>
                </div>
              )}
              
              <div>
                <Text strong>Remote Work:</Text>
                <br />
                <Tag color={job.remote_allowed ? 'green' : 'red'}>
                  {job.remote_allowed ? 'Allowed' : 'Not Allowed'}
                </Tag>
              </div>
              
              <div>
                <Text strong>Visa Sponsorship:</Text>
                <br />
                <Tag color={job.visa_sponsorship ? 'green' : 'red'}>
                  {job.visa_sponsorship ? 'Available' : 'Not Available'}
                </Tag>
              </div>
            </Space>
          </Card>

          {similarJobs && similarJobs.length > 0 && (
            <Card title="Similar Jobs">
              <List
                dataSource={similarJobs}
                renderItem={(similarJob) => (
                  <List.Item
                    style={{ cursor: 'pointer' }}
                    onClick={() => navigate(`/job/${similarJob.id}`)}
                  >
                    <List.Item.Meta
                      title={
                        <Text 
                          style={{ 
                            color: '#1890ff',
                            cursor: 'pointer'
                          }}
                        >
                          {similarJob.title}
                        </Text>
                      }
                      description={
                        <Space direction="vertical" size="small">
                          <Text type="secondary">{similarJob.company_name}</Text>
                          <Text type="secondary">
                            {similarJob.location.city}, {similarJob.location.state}
                          </Text>
                        </Space>
                      }
                    />
                  </List.Item>
                )}
              />
            </Card>
          )}
        </Col>
      </Row>

      {/* Job Application Modal */}
      <JobApplicationModal
        visible={applicationModalVisible}
        onClose={() => setApplicationModalVisible(false)}
        job={job}
        onApplicationSubmitted={handleApplicationSubmitted}
      />
    </div>
  );
};

export default JobDetailsPage;
