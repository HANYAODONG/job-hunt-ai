import React, { useState, useEffect } from 'react';
import { 
  Card, 
  Input, 
  Button, 
  Select, 
  Row, 
  Col, 
  Typography, 
  Space, 
  Tag, 
  Spin,
  Alert,
  Upload,
  message,
  Tooltip,
  Checkbox,
  Slider,
  Modal,
  Progress,
  Divider
} from 'antd';
import { 
  SearchOutlined, 
  UploadOutlined, 
  FilterOutlined, 
  StarOutlined,
  EnvironmentOutlined,
  DownOutlined,
  InfoCircleOutlined,
  DollarOutlined,
  ClockCircleOutlined,
  BulbOutlined,
  RobotOutlined
} from '@ant-design/icons';
import './SearchPage.css';
import { useQuery } from 'react-query';
import { 
  searchJobs, 
  searchJobsWithResume,
  extractKeywords,
  rerankWithKeywords,
  getRerankingExplanation,
} from '../services/api';
import JobApplicationModal from '../components/JobApplicationModal';
import RerankingScore from '../components/RerankingScore';
import { useAuth } from '../contexts/AuthContext';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;

const SearchPage = () => {
  const [searchQuery, setSearchQuery] = useState('');
  const [location, setLocation] = useState('');
  const [minSalary, setMinSalary] = useState([0, 300000]);
  const [jobType, setJobType] = useState([]);
  const [experienceLevel, setExperienceLevel] = useState('');
  const [remoteAllowed, setRemoteAllowed] = useState(null);
  const [visaSponsorship, setVisaSponsorship] = useState(null);
  const [resumeFile, setResumeFile] = useState(null);
  const [useResume, setUseResume] = useState(false);
  // Removed useReranking - initial search now ALWAYS uses regular search API
  // Keyword-based reranking is a separate feature triggered by "Rerank" button
  const [, setShowExplanations] = useState(false);
  const [applicationModalVisible, setApplicationModalVisible] = useState(false);
  const [selectedJob, setSelectedJob] = useState(null);
  const [aiExplanationModalVisible, setAiExplanationModalVisible] = useState(false);
  const [aiExplanationData, setAiExplanationData] = useState(null);
  const [loadingAiExplanation, setLoadingAiExplanation] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchRequest, setSearchRequest] = useState(null);
  const [sortBy, setSortBy] = useState('last_updated');
  const [extractedKeywords, setExtractedKeywords] = useState(null);
  const [selectedKeywords, setSelectedKeywords] = useState({
    job_titles: [],
    skills: [],
    salary: null,
    locations: []
  });
  const [selectedKeywordCategory, setSelectedKeywordCategory] = useState(null); // For dropdown
  const [selectedKeywordValue, setSelectedKeywordValue] = useState(null); // For dropdown
  const [, setIsExtractingKeywords] = useState(false);
  const [isReranking, setIsReranking] = useState(false);
  const [rerankedResults, setRerankedResults] = useState(null); // Store reranked results separately
  const { isAuthenticated, user } = useAuth();

  // Typewriter animation for "Hired"
  const [displayedText, setDisplayedText] = useState('');
  const [showDashes, setShowDashes] = useState(false);
  const [isTyping, setIsTyping] = useState(true);
  const fullText = 'Hired';

  useEffect(() => {
    let currentIndex = 0;
    const typingInterval = setInterval(() => {
      if (currentIndex < fullText.length) {
        setDisplayedText(fullText.substring(0, currentIndex + 1));
        currentIndex++;
      } else {
        clearInterval(typingInterval);
        setIsTyping(false);
        // Show dashes after text is complete
        setTimeout(() => {
          setShowDashes(true);
        }, 300);
      }
    }, 150); // Typing speed

    return () => clearInterval(typingInterval);
  }, []);

  const buildSearchParams = (queryText = searchQuery) => ({
    query: queryText,
    location: (location && location.trim()) || undefined,
    min_salary: minSalary[0] > 0 ? minSalary[0] : undefined,
    max_salary: minSalary[1] > 0 && minSalary[1] < 300000 ? minSalary[1] : undefined,
    job_type: jobType.length > 0 && jobType[0] ? jobType[0] : undefined,
    experience_level: (experienceLevel && experienceLevel.trim()) || undefined,
    remote_allowed: remoteAllowed !== null ? remoteAllowed : undefined,
    visa_sponsorship: visaSponsorship !== null ? visaSponsorship : undefined,
    page: 1,
    page_size: 20
  });

  const { data: initialSearchResults, isLoading, error } = useQuery(
    ['jobSearch', searchRequest, resumeFile],
    () => {
      const params = searchRequest?.params || buildSearchParams();
      // Initial search - ALWAYS use regular hybrid search (NO reranking yet)
      // Keyword reranking is a separate action triggered by user
      if (useResume && resumeFile) {
        return searchJobsWithResume(params, resumeFile);
      }
      return searchJobs(params);
    },
    {
      enabled: !!searchRequest, // Only run when the user submits a query
      retry: 1,
      onSuccess: (data) => {
        // Extract keywords AFTER search completes successfully
        const submittedQuery = searchRequest?.params?.query?.trim();
        if (submittedQuery) {
          handleExtractKeywords(submittedQuery);
        }
      }
    }
  );

  const handleExtractKeywords = async (query) => {
    setIsExtractingKeywords(true);
    try {
      const keywords = await extractKeywords(query);
      setExtractedKeywords(keywords);
      // Reset selected keywords
      setSelectedKeywords({
        job_titles: [],
        skills: [],
        salary: null,
        locations: []
      });
      setSelectedKeywordCategory(null);
      setSelectedKeywordValue(null);
    } catch (error) {
      console.error('Error extracting keywords:', error);
      setExtractedKeywords(null);
    } finally {
      setIsExtractingKeywords(false);
    }
  };

  // Use reranked results if available, otherwise use initial search results
  const currentSearchResults = rerankedResults || initialSearchResults;

  const handleSearch = async (queryOverride) => {
    // queryOverride may be a click event from onClick, not a string
    const effectiveQuery = (typeof queryOverride === 'string' ? queryOverride : searchQuery).trim();
    if (!effectiveQuery) {
      message.warning('Please enter a search query');
      return;
    }
    setHasSearched(true);
    setRerankedResults(null); // Clear previous reranked results
    setExtractedKeywords(null); // Clear previous keywords
    setSearchRequest({
      id: Date.now(),
      params: buildSearchParams(effectiveQuery)
    });
  };

  const handleExampleQuery = (query) => {
    setSearchQuery(query);
    handleSearch(query);
  };

  const handleKeywordSelect = (value) => {
    if (!value) {
      setSelectedKeywordCategory(null);
      setSelectedKeywordValue(null);
      setSelectedKeywords({
        job_titles: [],
        skills: [],
        salary: null,
        locations: []
      });
      return;
    }
    
    // Split only on the first colon to handle JSON values containing colons
    const firstColonIndex = value.indexOf(':');
    const category = value.substring(0, firstColonIndex);
    const val = value.substring(firstColonIndex + 1);
    setSelectedKeywordCategory(category);
    
    // Parse salary if needed
    let parsedValue = val;
    if (category === 'salary') {
      try {
        parsedValue = JSON.parse(val);
      } catch (e) {
        parsedValue = val;
      }
    }
    
    setSelectedKeywordValue(parsedValue);
    
    setSelectedKeywords(prev => {
      const newSelected = { ...prev };
      if (category === 'salary') {
        newSelected.salary = parsedValue;
      } else {
        // For other categories, replace the array with the selected value
        newSelected[category] = parsedValue ? [parsedValue] : [];
      }
      return newSelected;
    });
  };

  const handleRerankWithKeywords = async () => {
    if (!initialSearchResults || !initialSearchResults.jobs || initialSearchResults.jobs.length === 0) {
      message.warning('Please search for jobs first');
      return;
    }

    // Check if any keywords are selected
    const hasSelectedKeywords = 
      selectedKeywords.job_titles.length > 0 ||
      selectedKeywords.skills.length > 0 ||
      selectedKeywords.salary !== null ||
      selectedKeywords.locations.length > 0;

    if (!hasSelectedKeywords) {
      message.warning('Please select at least one keyword to rerank');
      return;
    }

    setIsReranking(true);
    try {
      // Call the separate rerank API with the initial search results
      const reranked = await rerankWithKeywords(initialSearchResults, selectedKeywords);
      setRerankedResults(reranked);
      message.success('Results reranked based on selected keywords!');
    } catch (error) {
      console.error('Error reranking with keywords:', error);
      message.error('Failed to rerank results');
    } finally {
      setIsReranking(false);
    }
  };

  // Use reranked results if available, otherwise use original search results
  // Use reranked results if available, otherwise initial search results
  const displayResults = currentSearchResults;

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
    setUseResume(true);
    message.success('Resume uploaded successfully!');
    return false; // Prevent auto upload
  };

  const clearFilters = () => {
    setLocation('');
    setMinSalary([0, 300000]);
    setJobType([]);
    setExperienceLevel('');
    setRemoteAllowed(null);
    setVisaSponsorship(null);
    setResumeFile(null);
    setUseResume(false);
    setShowExplanations(false);
  };

  const handleApplyToJob = (job) => {
    if (!isAuthenticated()) {
      message.warning('Please login to apply for jobs');
      return;
    }
    setSelectedJob(job);
    setApplicationModalVisible(true);
  };

  const handleApplicationSubmitted = () => {
    message.success('Application submitted successfully!');
  };

  const handleGetExplanation = async (jobId) => {
    try {
      // Call API with the current resume and search query for personalized explanation
      const explanation = await getRerankingExplanation(
        jobId, 
        searchQuery || null, 
        resumeFile
      );
      return explanation;
    } catch (error) {
      console.error('Failed to get explanation:', error);
      message.error('Failed to get job explanation');
      return null;
    }
  };

  const formatSalaryShort = (salary) => {
    if (!salary) return 'Not specified';
    const minSalary = Number(salary.min_salary) || 0;
    const maxSalary = Number(salary.max_salary) || 0;
    if (minSalary <= 0 && maxSalary <= 0) return 'Not specified';
    if (minSalary > 0 && maxSalary > 0) {
      const minK = (minSalary / 1000).toFixed(0);
      const maxK = (maxSalary / 1000).toFixed(0);
      return `$${minK}k - $${maxK}k`;
    }
    if (minSalary > 0) {
      return `$${(minSalary / 1000).toFixed(0)}k+`;
    }
    if (maxSalary > 0) {
      return `Up to $${(maxSalary / 1000).toFixed(0)}k`;
    }
    return 'Not specified';
  };

  const getJobCardColor = (index) => {
    const colors = [
      '#FFF4E6', // Light Orange
      '#E6F7FF', // Light Blue
      '#F6FFED', // Light Green
      '#FFF0F6', // Light Pink
      '#F0F5FF', // Light Purple
      '#FFFFFF'  // White
    ];
    return colors[index % colors.length];
  };

  const getCompanyLogo = (companyName) => {
    if (!companyName) return '💼';
    const firstLetter = companyName.charAt(0).toUpperCase();
    return firstLetter;
  };

  const formatDate = (dateString) => {
    if (!dateString) return 'Recently';
    try {
      const date = new Date(dateString);
      const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      return `${date.getDate()} ${months[date.getMonth()]}, ${date.getFullYear()}`;
    } catch {
      return 'Recently';
    }
  };

  return (
    <div className="search-page-container">
      {/* Always Visible Search Box - Simple when no search, with filters after search */}
      <div className="top-search-bar">
        <div className="top-search-container">
          <div className="search-page-title-section">
            <Title level={1} className="fancy-search-title">
              Hey {isAuthenticated() && user?.first_name ? user.first_name : 'Mate'}, Lets Get you <span className={`hired-highlight ${showDashes ? 'show-dashes' : ''} ${isTyping ? 'typing' : ''}`}>{displayedText}</span> !
            </Title>
          </div>
          <Card className="top-search-card">
            <div className="search-bar-wrapper">
              <div className="search-input-container">
                <TextArea
                  className="search-bar-textarea"
                  placeholder="Describe your ideal job... (e.g., 'I want to work as a software developer solving bugs and researching AI topics in California with H1B sponsorship')"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onPressEnter={(e) => {
                    if (e.shiftKey) return;
                    e.preventDefault();
                    handleSearch();
                  }}
                  autoSize={{ minRows: 3, maxRows: 8 }}
                  allowClear
                />
                <div className="search-actions-icons">
                  <Tooltip title="Resume Upload">
                    <Upload
                      beforeUpload={handleResumeUpload}
                      showUploadList={false}
                      accept=".pdf,.doc,.docx"
                    >
                      <Button
                        className="resume-icon-btn"
                        icon={<UploadOutlined />}
                        type={useResume ? 'primary' : 'text'}
                        shape="circle"
                        size="large"
                      />
                    </Upload>
                  </Tooltip>
                  <Tooltip title="Search">
                    <Button
                      className="search-icon-btn"
                      type="primary"
                      icon={<SearchOutlined />}
                      onClick={handleSearch}
                      loading={isLoading}
                      shape="circle"
                      size="large"
                    />
                  </Tooltip>
                </div>
              </div>
            </div>
            
            {/* Filters Below Search Bar - Only show after search */}
            {hasSearched && (
              <Row gutter={16} style={{ marginTop: 12 }}>
                <Col>
                  <Select
                    placeholder="Work location"
                    value={location || undefined}
                    onChange={setLocation}
                    allowClear
                    className="filter-select"
                    style={{ minWidth: 150 }}
                  >
                    <Option value="San Francisco, CA">San Francisco, CA</Option>
                    <Option value="New York, NY">New York, NY</Option>
                    <Option value="Seattle, WA">Seattle, WA</Option>
                    <Option value="Austin, TX">Austin, TX</Option>
                    <Option value="Boston, MA">Boston, MA</Option>
                    <Option value="Los Angeles, CA">Los Angeles, CA</Option>
                    <Option value="Remote">Remote</Option>
                  </Select>
                </Col>
                <Col>
                  <Select
                    placeholder="Experience"
                    value={experienceLevel || undefined}
                    onChange={setExperienceLevel}
                    allowClear
                    className="filter-select"
                    style={{ minWidth: 140 }}
                  >
                    <Option value="entry">Entry Level</Option>
                    <Option value="mid">Mid Level</Option>
                    <Option value="senior">Senior Level</Option>
                    <Option value="executive">Executive</Option>
                  </Select>
                </Col>
                <Col flex="auto">
                  <div className="salary-range-top">
                    <Text className="salary-label-top">Salary range</Text>
                    <Slider
                      className="salary-slider-top"
                      range
                      min={0}
                      max={300000}
                      step={1000}
                      value={minSalary}
                      onChange={setMinSalary}
                      tooltip={{
                        formatter: (value) => `$${value?.toLocaleString()}`
                      }}
                    />
                    <Text className="salary-value-top">
                      ${minSalary[0]?.toLocaleString()} - ${minSalary[1]?.toLocaleString()}
                    </Text>
                  </div>
                </Col>
              </Row>
            )}
          </Card>
        </div>
      </div>

      {/* Example Queries Section - Show when no search */}
      {!hasSearched && (
        <div className="elaborated-queries-section">
          <div className="elaborated-queries-container">
            <Title level={4} className="elaborated-queries-title">
              Example Queries to Help You Get Started
            </Title>
            <div className="elaborated-queries-grid">
              <div className="elaborated-query-card">
                <Text className="query-example-label">Role & Location</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('I want to work as a senior software engineer in San Francisco, California')}
                >
                  I want to work as a senior software engineer in San Francisco, California
                </div>
                <Text className="query-example-description">
                  Specify job title, experience level, and location
                </Text>
              </div>

              <div className="elaborated-query-card">
                <Text className="query-example-label">Skills & Technologies</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('Looking for a backend developer role using Python, Django, and PostgreSQL with experience in microservices architecture')}
                >
                  Looking for a backend developer role using Python, Django, and PostgreSQL with experience in microservices architecture
                </div>
                <Text className="query-example-description">
                  Mention specific technologies, frameworks, or skills you want to work with
                </Text>
              </div>

              <div className="elaborated-query-card">
                <Text className="query-example-label">Remote Work & Benefits</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('Remote product manager position with flexible hours, health insurance, and stock options')}
                >
                  Remote product manager position with flexible hours, health insurance, and stock options
                </div>
                <Text className="query-example-description">
                  Include work preferences, benefits, or company culture aspects
                </Text>
              </div>

              <div className="elaborated-query-card">
                <Text className="query-example-label">Visa Sponsorship</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('Machine learning engineer position in Seattle, Washington with H1B visa sponsorship and relocation assistance')}
                >
                  Machine learning engineer position in Seattle, Washington with H1B visa sponsorship and relocation assistance
                </div>
                <Text className="query-example-description">
                  Specify visa requirements and any relocation needs
                </Text>
              </div>

              <div className="elaborated-query-card">
                <Text className="query-example-label">Industry & Domain</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('Data analyst role in fintech or healthcare industry working with large datasets and SQL')}
                >
                  Data analyst role in fintech or healthcare industry working with large datasets and SQL
                </div>
                <Text className="query-example-description">
                  Mention industry preferences or domain expertise
                </Text>
              </div>

              <div className="elaborated-query-card">
                <Text className="query-example-label">Salary & Compensation</Text>
                <div 
                  className="query-example-text"
                  onClick={() => handleExampleQuery('Senior full stack developer position paying $150k+ annually with equity and bonus structure')}
                >
                  Senior full stack developer position paying $150k+ annually with equity and bonus structure
                </div>
                <Text className="query-example-description">
                  Include salary expectations or compensation details
                </Text>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Results Section */}
      {hasSearched && (
        <>
          {/* Results Header */}
          <div className="results-header-simple">
            {displayResults && (
              <Text className="jobs-found-text">
                Found <span className="jobs-count-blue">{displayResults.total_count}</span> <span className="jobs-count-blue">jobs</span>
                {rerankedResults && <span style={{ marginLeft: 8, color: '#52c41a' }}>(Reranked)</span>}
              </Text>
            )}
            <Space>
              {/* Keyword Dropdown */}
              {extractedKeywords && (
                <Select
                  placeholder="Select keyword to rerank"
                  value={selectedKeywordValue && selectedKeywordCategory 
                    ? `${selectedKeywordCategory}:${selectedKeywordCategory === 'salary' ? JSON.stringify(selectedKeywordValue) : selectedKeywordValue}` 
                    : null}
                  onChange={handleKeywordSelect}
                  style={{ minWidth: 200 }}
                  suffixIcon={<DownOutlined />}
                  allowClear
                >
                  {/* Job Titles */}
                  {extractedKeywords.job_titles && extractedKeywords.job_titles.length > 0 && (
                    <Select.OptGroup label="Job Titles">
                      {extractedKeywords.job_titles.map((title, index) => (
                        <Option key={`job_titles:${title}`} value={`job_titles:${title}`}>
                          {title}
                        </Option>
                      ))}
                    </Select.OptGroup>
                  )}
                  
                  {/* Skills */}
                  {extractedKeywords.skills && extractedKeywords.skills.length > 0 && (
                    <Select.OptGroup label="Skills">
                      {extractedKeywords.skills.map((skill, index) => (
                        <Option key={`skills:${skill}`} value={`skills:${skill}`}>
                          {skill}
                        </Option>
                      ))}
                    </Select.OptGroup>
                  )}
                  
                  {/* Salary */}
                  {extractedKeywords.salary && (
                    <Option value={`salary:${JSON.stringify(extractedKeywords.salary)}`}>
                      Salary: ${extractedKeywords.salary.min?.toLocaleString()} - ${extractedKeywords.salary.max?.toLocaleString()}
                    </Option>
                  )}
                  
                  {/* Locations */}
                  {extractedKeywords.locations && extractedKeywords.locations.length > 0 && (
                    <Select.OptGroup label="Locations">
                      {extractedKeywords.locations.map((location, index) => (
                        <Option key={`locations:${location}`} value={`locations:${location}`}>
                          {location}
                        </Option>
                      ))}
                    </Select.OptGroup>
                  )}
                </Select>
              )}
              
              {/* Rerank Button */}
              {extractedKeywords && (
                <Button
                  type="primary"
                  onClick={handleRerankWithKeywords}
                  loading={isReranking}
                  disabled={!selectedKeywordValue}
                >
                  Rerank
                </Button>
              )}
              
              {/* Sort Dropdown */}
              <Select
                className="sort-select-simple"
                value={sortBy}
                onChange={setSortBy}
                suffixIcon={<DownOutlined />}
              >
                <Option value="last_updated">Last updated</Option>
                <Option value="relevance">Relevance</Option>
                <Option value="salary_high">Salary: High to Low</Option>
                <Option value="salary_low">Salary: Low to High</Option>
                <Option value="date_new">Date: Newest</Option>
              </Select>
            </Space>
          </div>

          {/* Main Content Area */}
          <div className="search-content-wrapper">
            <div className="search-content">
              {/* Left Sidebar */}
              <div className="sidebar-filters">
            {/* Smart Search Options Card */}
            <Card className="filter-card">
              <Title level={5} className="filter-card-title">
                <StarOutlined /> Smart Search
              </Title>
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                <Text type="secondary" style={{ fontSize: '12px' }}>
                  Use keywords dropdown to rerank results after initial search
                </Text>
                <Upload
                  beforeUpload={handleResumeUpload}
                  showUploadList={false}
                  accept=".pdf,.doc,.docx"
                >
                  <Button
                    icon={<UploadOutlined />}
                    size="small"
                    type={useResume ? 'primary' : 'default'}
                    block
                  >
                    {useResume ? 'Resume Uploaded ✓' : 'Upload Resume'}
                  </Button>
                </Upload>
              </Space>
            </Card>

            {/* Working Schedule Filter */}
            <Card className="filter-card">
              <Title level={5} className="filter-card-title">
                <FilterOutlined /> Working Schedule
              </Title>
              <Checkbox.Group
                value={jobType}
                onChange={setJobType}
                style={{ width: '100%' }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Checkbox value="full_time">Full time</Checkbox>
                  <Checkbox value="part_time">Part time</Checkbox>
                  <Checkbox value="contract">Project work</Checkbox>
                  <Checkbox value="internship">Internship</Checkbox>
                </Space>
              </Checkbox.Group>
            </Card>

            {/* Employment Type Filter */}
            <Card className="filter-card">
              <Title level={5} className="filter-card-title">
                Employment Type
              </Title>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Checkbox
                  checked={remoteAllowed === true}
                  onChange={(e) => setRemoteAllowed(e.target.checked ? true : null)}
                >
                  Distant work
                </Checkbox>
                <Checkbox
                  checked={remoteAllowed === false}
                  onChange={(e) => setRemoteAllowed(e.target.checked ? false : null)}
                >
                  On-site
                </Checkbox>
                <Checkbox
                  checked={visaSponsorship === true}
                  onChange={(e) => setVisaSponsorship(e.target.checked ? true : null)}
                >
                  Visa Sponsorship
                </Checkbox>
              </Space>
            </Card>

            <Button onClick={clearFilters} block style={{ marginTop: 16 }}>
              Clear Filters
            </Button>
          </div>

          {/* Main Content */}
          <div className="main-content-area">
            {isLoading && (
              <div className="loading-container">
                <Spin size="large" />
              </div>
            )}

            {error && (
              <Alert
                message="Search Error"
                description="There was an error searching for jobs. Please try again."
                type="error"
                showIcon
                style={{ marginBottom: 24 }}
              />
            )}

            {initialSearchResults && initialSearchResults.is_mock_data && (
              <Alert
                message="Demo Mode - Using Mock Data"
                description="The backend is currently unavailable. You are viewing sample job listings for UI/UX testing purposes."
                type="warning"
                showIcon
                style={{ marginBottom: 24 }}
                closable
              />
            )}

            {displayResults && displayResults.jobs.length === 0 && (
              <Alert
                message="No jobs found"
                description="Try adjusting your search criteria or filters."
                type="info"
                showIcon
              />
            )}

            {displayResults && displayResults.jobs.length > 0 && (
              <>
                {/* Reranking Statistics */}
                {displayResults.reranking_statistics && (
                  <Card className="stats-card">
                    <Row gutter={16}>
                      <Col span={6}>
                        <Text className="stat-label">Average Match</Text>
                        <Text className="stat-value stat-high">
                          {(displayResults.reranking_statistics.average_score * 100).toFixed(1)}%
                        </Text>
                      </Col>
                      <Col span={6}>
                        <Text className="stat-label">High Quality</Text>
                        <Text className="stat-value stat-high">
                          {displayResults.reranking_statistics.high_quality_matches}
                        </Text>
                      </Col>
                      <Col span={6}>
                        <Text className="stat-label">Medium Quality</Text>
                        <Text className="stat-value stat-medium">
                          {displayResults.reranking_statistics.medium_quality_matches}
                        </Text>
                      </Col>
                      <Col span={6}>
                        <Text className="stat-label">Low Quality</Text>
                        <Text className="stat-value stat-low">
                          {displayResults.reranking_statistics.low_quality_matches}
                        </Text>
                      </Col>
                    </Row>
                  </Card>
                )}

                {/* Job Cards Grid */}
                <div className="job-cards-grid">
                  {displayResults.jobs.map((job, index) => (
                    <Card
                      key={job.id}
                      className="job-card-luckyjob"
                      style={{ backgroundColor: getJobCardColor(index) }}
                      hoverable
                    >
                      {/* Header: Logo on left, Match Badge on right */}
                      <div className="job-card-header-luckyjob">
                        <div className="company-logo-luckyjob">
                          {getCompanyLogo(job.company_name)}
                        </div>
                        
                        {/* Show match badge when searching with resume, OR show AI analysis button for query-only */}
                        <div className="match-badge-container-luckyjob">
                          {useResume && resumeFile && (job.rerank_score !== undefined || job.match_score !== undefined || job.similarity_score !== undefined) ? (
                            // Pipeline B: Resume + Query - show full score badge
                            <RerankingScore 
                              score={job.rerank_score || job.match_score || job.similarity_score || 0}
                              showDetails={true}
                              jobId={job.id}
                              onGetExplanation={handleGetExplanation}
                              compact={true}
                            />
                          ) : hasSearched && searchQuery ? (
                            // Pipeline A: Query-only - show AI analysis button
                            <Tooltip title="Get AI-powered match analysis based on your search query">
                              <Button
                                type="primary"
                                size="small"
                                icon={<InfoCircleOutlined />}
                                loading={loadingAiExplanation && selectedJob?.id === job.id}
                                onClick={async () => {
                                  setSelectedJob(job);
                                  setLoadingAiExplanation(true);
                                  try {
                                    const data = await handleGetExplanation(job.id);
                                    if (data) {
                                      setAiExplanationData(data);
                                      setAiExplanationModalVisible(true);
                                    }
                                  } finally {
                                    setLoadingAiExplanation(false);
                                  }
                                }}
                                style={{ 
                                  background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                  border: 'none',
                                  borderRadius: '8px'
                                }}
                              >
                                AI Match
                              </Button>
                            </Tooltip>
                          ) : null}
                        </div>
                      </div>
                      
                      {/* Body: Title, Company, Details, Tags */}
                      <div className="job-card-body-luckyjob">
                        <Title level={4} className="job-title-luckyjob">{job.title}</Title>
                        <Text className="company-name-luckyjob">{job.company_name}</Text>

                        {/* Job Details with Icons */}
                        <div className="job-details-luckyjob">
                          <div className="job-detail-item-luckyjob">
                            <EnvironmentOutlined className="job-detail-icon-luckyjob" />
                            <Text className="job-location-luckyjob">
                              {job.location?.city || job.location || 'Location not specified'}, {job.location?.state || ''}
                            </Text>
                          </div>
                          <div className="job-detail-item-luckyjob">
                            <DollarOutlined className="job-detail-icon-luckyjob" />
                            <Text className="salary-amount-luckyjob">
                              {formatSalaryShort(job.salary)}
                            </Text>
                          </div>
                          <div className="job-detail-item-luckyjob">
                            <ClockCircleOutlined className="job-detail-icon-luckyjob" />
                            <Text className="job-date-luckyjob">
                              {formatDate(job.posted_date || job.created_at)}
                            </Text>
                          </div>
                        </div>

                        {/* Tags */}
                        <div className="job-tags-luckyjob">
                          {job.job_type && (
                            <Tag className="job-tag-luckyjob">
                              {job.job_type.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </Tag>
                          )}
                          {job.experience_level && (
                            <Tag className="job-tag-luckyjob">
                              {job.experience_level.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                            </Tag>
                          )}
                          {job.remote_allowed && <Tag className="job-tag-remote-luckyjob">Remote</Tag>}
                          {job.visa_sponsorship && <Tag className="job-tag-luckyjob">H1B Sponsor</Tag>}
                        </div>
                      </div>

                      {/* Footer: View Details Button */}
                      <div className="job-card-footer-luckyjob">
                        <Button 
                          type="primary" 
                          className="details-button-luckyjob"
                          block
                          onClick={() => handleApplyToJob(job)}
                        >
                          View Details
                        </Button>
                      </div>
                    </Card>
                  ))}
                </div>
              </>
            )}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Job Application Modal */}
      <JobApplicationModal
        visible={applicationModalVisible}
        onClose={() => setApplicationModalVisible(false)}
        job={selectedJob}
        onApplicationSubmitted={handleApplicationSubmitted}
      />

      {/* AI Match Explanation Modal */}
      <Modal
        title={
          <Space>
            <RobotOutlined style={{ color: '#667eea' }} />
            <span>AI-Powered Match Analysis</span>
            {aiExplanationData?.scoring_method && (
              <Tag color="purple" style={{ marginLeft: 8 }}>
                {aiExplanationData.scoring_method.includes('Query-only') ? 'Query Analysis' : 'Full Analysis'}
              </Tag>
            )}
          </Space>
        }
        open={aiExplanationModalVisible}
        onCancel={() => {
          setAiExplanationModalVisible(false);
          setAiExplanationData(null);
        }}
        footer={null}
        width={800}
      >
        {aiExplanationData && (
          <div>
            {/* Job Info */}
            <Card size="small" style={{ marginBottom: 16, background: '#fafafa' }}>
              <Row gutter={16}>
                <Col span={12}>
                  <Text strong>Job Title:</Text>
                  <br />
                  <Text style={{ fontSize: '16px' }}>{aiExplanationData.job_title}</Text>
                </Col>
                <Col span={12}>
                  <Text strong>Company:</Text>
                  <br />
                  <Text style={{ fontSize: '16px' }}>{aiExplanationData.company}</Text>
                </Col>
              </Row>
              <Divider style={{ margin: '12px 0' }} />
              <Row gutter={16}>
                <Col span={8}>
                  <Text strong>Overall Match:</Text>
                  <br />
                  <Progress 
                    percent={Math.round(aiExplanationData.final_score * 100)} 
                    strokeColor={
                      aiExplanationData.final_score >= 0.7 ? '#52c41a' : 
                      aiExplanationData.final_score >= 0.5 ? '#faad14' : '#ff4d4f'
                    }
                  />
                </Col>
                <Col span={8}>
                  <Text strong>Match Quality:</Text>
                  <br />
                  <Tag 
                    color={
                      aiExplanationData.final_score >= 0.7 ? 'green' : 
                      aiExplanationData.final_score >= 0.5 ? 'orange' : 'red'
                    }
                    style={{ marginTop: 4 }}
                  >
                    {aiExplanationData.final_score >= 0.7 ? 'Strong Match' : 
                     aiExplanationData.final_score >= 0.5 ? 'Moderate Match' : 'Weak Match'}
                  </Tag>
                </Col>
                <Col span={8}>
                  <Text strong>Analysis Type:</Text>
                  <br />
                  <Tag color="purple" style={{ marginTop: 4 }}>
                    🤖 {aiExplanationData.scoring_method || 'AI Analysis'}
                  </Tag>
                </Col>
              </Row>
            </Card>

            {/* Knowledge Graph Insight */}
            {aiExplanationData.knowledge_graph_explanation && (
              <Alert
                message={<Text strong>🔗 Knowledge Graph Insight</Text>}
                description={aiExplanationData.knowledge_graph_explanation}
                type="info"
                style={{ marginBottom: 16 }}
              />
            )}

            {/* Factor Breakdown */}
            <Title level={5}>
              <BulbOutlined style={{ marginRight: 8 }} />
              AI Analysis Breakdown
            </Title>
            {aiExplanationData.factor_scores && Object.entries(aiExplanationData.factor_scores).map(([factor, data]) => (
              <Card 
                key={factor} 
                size="small" 
                style={{ 
                  marginBottom: 8,
                  borderLeft: `4px solid ${data.score >= 0.7 ? '#52c41a' : data.score >= 0.4 ? '#faad14' : '#ff4d4f'}`
                }}
              >
                <Row gutter={16} align="middle">
                  <Col span={6}>
                    <Text strong>{data.name || factor.replace(/_/g, ' ')}</Text>
                    <br />
                    <Text type="secondary" style={{ fontSize: '11px' }}>
                      Weight: {(data.weight * 100).toFixed(0)}%
                    </Text>
                  </Col>
                  <Col span={4}>
                    <Progress 
                      percent={Math.round(data.score * 100)} 
                      size="small"
                      strokeColor={data.score >= 0.7 ? '#52c41a' : data.score >= 0.4 ? '#faad14' : '#ff4d4f'}
                    />
                  </Col>
                  <Col span={14}>
                    <div style={{ 
                      background: '#f5f5f5', 
                      padding: '8px 12px', 
                      borderRadius: '4px',
                      fontSize: '13px'
                    }}>
                      {data.explanation}
                    </div>
                  </Col>
                </Row>
              </Card>
            ))}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default SearchPage;
