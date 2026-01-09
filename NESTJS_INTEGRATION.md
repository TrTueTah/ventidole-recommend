# NestJS Integration Guide

Complete guide for integrating the FastAPI Recommendation Service with your NestJS backend.

## Table of Contents

1. [Setup](#setup)
2. [Service Implementation](#service-implementation)
3. [Controller Implementation](#controller-implementation)
4. [Error Handling](#error-handling)
5. [Caching](#caching)
6. [Health Checks](#health-checks)
7. [Complete Example](#complete-example)

---

## Setup

### 1. Install Dependencies

```bash
# In your NestJS project
npm install @nestjs/axios axios
npm install --save-dev @types/node
```

### 2. Environment Configuration

Add to your `.env` file:

```bash
# Recommendation Service
RECOMMENDATION_API_URL=http://localhost:8000
RECOMMENDATION_API_TIMEOUT=5000
RECOMMENDATION_CACHE_TTL=300
```

### 3. Configuration Module

Create `src/config/recommendation.config.ts`:

```typescript
import { registerAs } from '@nestjs/config';

export default registerAs('recommendation', () => ({
  apiUrl: process.env.RECOMMENDATION_API_URL || 'http://localhost:8000',
  timeout: parseInt(process.env.RECOMMENDATION_API_TIMEOUT, 10) || 5000,
  cacheTtl: parseInt(process.env.RECOMMENDATION_CACHE_TTL, 10) || 300,
}));
```

---

## Service Implementation

### Basic Service

Create `src/recommendation/recommendation.service.ts`:

```typescript
import { Injectable, Logger, HttpException, HttpStatus } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';
import { AxiosError } from 'axios';

// DTOs
export interface PostRecommendation {
  post_id: string;
  score: number;
  metadata: {
    tags?: string[];
    communityId?: string;
    [key: string]: any;
  };
}

export interface PaginationMetadata {
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface RecommendationResponse {
  user_id: string;
  recommendations: PostRecommendation[];
  pagination: PaginationMetadata;
}

export interface HealthCheckResponse {
  status: string;
  timestamp: string;
  checks: {
    [key: string]: {
      status: string;
      message: string;
      response_time_ms?: number;
    };
  };
}

@Injectable()
export class RecommendationService {
  private readonly logger = new Logger(RecommendationService.name);
  private readonly apiUrl: string;
  private readonly timeout: number;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.apiUrl = this.configService.get<string>('recommendation.apiUrl');
    this.timeout = this.configService.get<number>('recommendation.timeout');
  }

  /**
   * Get personalized recommendations for a user
   */
  async getUserRecommendations(
    userId: string,
    limit: number = 20,
    offset: number = 0,
  ): Promise<RecommendationResponse> {
    try {
      this.logger.debug(
        `Fetching recommendations for user ${userId} (limit=${limit}, offset=${offset})`,
      );

      const response = await firstValueFrom(
        this.httpService.get<RecommendationResponse>(
          `${this.apiUrl}/recommendations/${userId}`,
          {
            params: { limit, offset },
            timeout: this.timeout,
          },
        ),
      );

      this.logger.debug(
        `Retrieved ${response.data.recommendations.length} recommendations for user ${userId}`,
      );

      return response.data;
    } catch (error) {
      return this.handleRecommendationError(error, userId);
    }
  }

  /**
   * Check if recommendation service is healthy
   */
  async checkHealth(): Promise<HealthCheckResponse> {
    try {
      const response = await firstValueFrom(
        this.httpService.get<HealthCheckResponse>(`${this.apiUrl}/health`, {
          timeout: this.timeout,
        }),
      );

      return response.data;
    } catch (error) {
      this.logger.error('Health check failed', error);
      throw new HttpException(
        'Recommendation service is unavailable',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }
  }

  /**
   * Trigger model reload (admin endpoint)
   */
  async reloadModel(): Promise<any> {
    try {
      this.logger.log('Triggering model reload...');

      const response = await firstValueFrom(
        this.httpService.post(`${this.apiUrl}/admin/reload-model`, null, {
          timeout: 30000, // Longer timeout for reload
        }),
      );

      this.logger.log('Model reload completed', response.data);
      return response.data;
    } catch (error) {
      this.logger.error('Model reload failed', error);
      throw new HttpException(
        'Failed to reload recommendation model',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * Get model status
   */
  async getModelStatus(): Promise<any> {
    try {
      const response = await firstValueFrom(
        this.httpService.get(`${this.apiUrl}/admin/model-status`, {
          timeout: this.timeout,
        }),
      );

      return response.data;
    } catch (error) {
      this.logger.error('Failed to get model status', error);
      throw new HttpException(
        'Failed to get model status',
        HttpStatus.INTERNAL_SERVER_ERROR,
      );
    }
  }

  /**
   * Handle errors from recommendation API
   */
  private handleRecommendationError(
    error: any,
    userId: string,
  ): RecommendationResponse {
    if (error.response) {
      const status = error.response.status;
      const errorData = error.response.data;

      // User not found - return empty recommendations
      if (status === 404) {
        this.logger.warn(
          `User ${userId} not found in recommendation system`,
        );
        return {
          user_id: userId,
          recommendations: [],
          pagination: {
            total: 0,
            limit: 20,
            offset: 0,
            has_more: false,
          },
        };
      }

      // Service unavailable
      if (status === 503) {
        this.logger.error(
          `Recommendation service unavailable: ${errorData?.detail}`,
        );
        throw new HttpException(
          'Recommendation service is temporarily unavailable',
          HttpStatus.SERVICE_UNAVAILABLE,
        );
      }
    }

    // Network error or timeout
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
      this.logger.error('Cannot connect to recommendation service', error);
      throw new HttpException(
        'Recommendation service is unreachable',
        HttpStatus.SERVICE_UNAVAILABLE,
      );
    }

    // Generic error
    this.logger.error('Unexpected error from recommendation service', error);
    throw new HttpException(
      'Failed to fetch recommendations',
      HttpStatus.INTERNAL_SERVER_ERROR,
    );
  }
}
```

---

## Service with Caching

Enhanced service with Redis caching:

```typescript
import { Injectable, Logger, Inject, CACHE_MANAGER } from '@nestjs/common';
import { Cache } from 'cache-manager';

@Injectable()
export class RecommendationServiceWithCache {
  private readonly logger = new Logger(RecommendationServiceWithCache.name);
  private readonly apiUrl: string;
  private readonly timeout: number;
  private readonly cacheTtl: number;

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject(CACHE_MANAGER) private readonly cacheManager: Cache,
  ) {
    this.apiUrl = this.configService.get<string>('recommendation.apiUrl');
    this.timeout = this.configService.get<number>('recommendation.timeout');
    this.cacheTtl = this.configService.get<number>('recommendation.cacheTtl');
  }

  async getUserRecommendations(
    userId: string,
    limit: number = 20,
    offset: number = 0,
  ): Promise<RecommendationResponse> {
    const cacheKey = `recommendations:${userId}:${limit}:${offset}`;

    try {
      // Try to get from cache first
      const cached = await this.cacheManager.get<RecommendationResponse>(
        cacheKey,
      );

      if (cached) {
        this.logger.debug(`Cache hit for user ${userId}`);
        return cached;
      }

      this.logger.debug(`Cache miss for user ${userId}, fetching from API`);

      // Fetch from API
      const response = await firstValueFrom(
        this.httpService.get<RecommendationResponse>(
          `${this.apiUrl}/recommendations/${userId}`,
          {
            params: { limit, offset },
            timeout: this.timeout,
          },
        ),
      );

      // Store in cache
      await this.cacheManager.set(cacheKey, response.data, this.cacheTtl);

      return response.data;
    } catch (error) {
      // If API fails and we have cached data (even if expired), return it
      const cached = await this.cacheManager.get<RecommendationResponse>(
        cacheKey,
      );
      if (cached) {
        this.logger.warn(
          `API failed, returning stale cache for user ${userId}`,
        );
        return cached;
      }

      return this.handleRecommendationError(error, userId);
    }
  }

  /**
   * Invalidate cache for a user (call after user interactions)
   */
  async invalidateUserCache(userId: string): Promise<void> {
    const pattern = `recommendations:${userId}:*`;
    // Note: This requires a custom cache store that supports pattern deletion
    // Or you can track cache keys separately
    this.logger.debug(`Invalidating cache for user ${userId}`);
  }

  // ... rest of the methods from basic service
}
```

---

## Controller Implementation

Create `src/recommendation/recommendation.controller.ts`:

```typescript
import {
  Controller,
  Get,
  Post,
  Query,
  Param,
  HttpCode,
  HttpStatus,
  UseGuards,
} from '@nestjs/common';
import { RecommendationService } from './recommendation.service';
import { JwtAuthGuard } from '../auth/jwt-auth.guard'; // Your auth guard
import { CurrentUser } from '../auth/current-user.decorator'; // Your user decorator

@Controller('recommendations')
@UseGuards(JwtAuthGuard) // Protect endpoints
export class RecommendationController {
  constructor(
    private readonly recommendationService: RecommendationService,
  ) {}

  /**
   * Get recommendations for the current user
   * GET /recommendations
   */
  @Get()
  async getCurrentUserRecommendations(
    @CurrentUser() user: any,
    @Query('limit') limit: number = 20,
    @Query('offset') offset: number = 0,
  ) {
    return this.recommendationService.getUserRecommendations(
      user.id,
      limit,
      offset,
    );
  }

  /**
   * Get recommendations for a specific user (admin)
   * GET /recommendations/:userId
   */
  @Get(':userId')
  async getUserRecommendations(
    @Param('userId') userId: string,
    @Query('limit') limit: number = 20,
    @Query('offset') offset: number = 0,
  ) {
    return this.recommendationService.getUserRecommendations(
      userId,
      limit,
      offset,
    );
  }

  /**
   * Health check endpoint
   * GET /recommendations/health
   */
  @Get('health')
  async checkHealth() {
    return this.recommendationService.checkHealth();
  }
}

/**
 * Admin controller for model management
 */
@Controller('admin/recommendations')
@UseGuards(JwtAuthGuard) // Add admin role guard
export class RecommendationAdminController {
  constructor(
    private readonly recommendationService: RecommendationService,
  ) {}

  /**
   * Reload recommendation model
   * POST /admin/recommendations/reload
   */
  @Post('reload')
  @HttpCode(HttpStatus.OK)
  async reloadModel() {
    return this.recommendationService.reloadModel();
  }

  /**
   * Get model status
   * GET /admin/recommendations/status
   */
  @Get('status')
  async getModelStatus() {
    return this.recommendationService.getModelStatus();
  }
}
```

---

## Module Configuration

Create `src/recommendation/recommendation.module.ts`:

```typescript
import { Module } from '@nestjs/common';
import { HttpModule } from '@nestjs/axios';
import { ConfigModule } from '@nestjs/config';
import { CacheModule } from '@nestjs/cache-manager';
import { RecommendationService } from './recommendation.service';
import { RecommendationController, RecommendationAdminController } from './recommendation.controller';
import recommendationConfig from '../config/recommendation.config';

@Module({
  imports: [
    HttpModule,
    ConfigModule.forFeature(recommendationConfig),
    CacheModule.register({
      ttl: 300, // 5 minutes
      max: 1000, // Maximum number of items in cache
    }),
  ],
  controllers: [RecommendationController, RecommendationAdminController],
  providers: [RecommendationService],
  exports: [RecommendationService],
})
export class RecommendationModule {}
```

Add to `app.module.ts`:

```typescript
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { RecommendationModule } from './recommendation/recommendation.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [recommendationConfig],
    }),
    RecommendationModule,
    // ... other modules
  ],
})
export class AppModule {}
```

---

## Error Handling

### Fallback Strategy

Create `src/recommendation/recommendation-fallback.service.ts`:

```typescript
import { Injectable, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Post } from '../posts/entities/post.entity';

@Injectable()
export class RecommendationFallbackService {
  private readonly logger = new Logger(RecommendationFallbackService.name);

  constructor(
    @InjectRepository(Post)
    private readonly postRepository: Repository<Post>,
  ) {}

  /**
   * Get trending posts as fallback when recommendation service fails
   */
  async getTrendingPosts(limit: number = 20): Promise<Post[]> {
    this.logger.warn('Using fallback: trending posts');

    return this.postRepository.find({
      order: {
        viewCount: 'DESC',
        createdAt: 'DESC',
      },
      take: limit,
      relations: ['community', 'author'],
    });
  }

  /**
   * Get posts from user's followed communities
   */
  async getPostsFromFollowedCommunities(
    userId: string,
    limit: number = 20,
  ): Promise<Post[]> {
    this.logger.warn('Using fallback: posts from followed communities');

    return this.postRepository
      .createQueryBuilder('post')
      .innerJoin('community_follower', 'cf', 'cf.communityId = post.communityId')
      .where('cf.userId = :userId', { userId })
      .andWhere('cf.isActive = true')
      .orderBy('post.createdAt', 'DESC')
      .limit(limit)
      .getMany();
  }
}
```

### Enhanced Service with Fallback

```typescript
@Injectable()
export class RecommendationService {
  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    private readonly fallbackService: RecommendationFallbackService,
  ) {}

  async getUserRecommendations(
    userId: string,
    limit: number = 20,
    offset: number = 0,
  ): Promise<RecommendationResponse> {
    try {
      // Try to get from recommendation service
      const response = await firstValueFrom(
        this.httpService.get<RecommendationResponse>(
          `${this.apiUrl}/recommendations/${userId}`,
          {
            params: { limit, offset },
            timeout: this.timeout,
          },
        ),
      );

      return response.data;
    } catch (error) {
      // If user not found (404), use fallback
      if (error.response?.status === 404) {
        this.logger.warn(
          `User ${userId} not in recommendation system, using fallback`,
        );
        return this.getFallbackRecommendations(userId, limit, offset);
      }

      // If service unavailable (503), use fallback
      if (error.response?.status === 503) {
        this.logger.error('Recommendation service unavailable, using fallback');
        return this.getFallbackRecommendations(userId, limit, offset);
      }

      throw error;
    }
  }

  private async getFallbackRecommendations(
    userId: string,
    limit: number,
    offset: number,
  ): Promise<RecommendationResponse> {
    // Try user's followed communities first
    let posts = await this.fallbackService.getPostsFromFollowedCommunities(
      userId,
      limit,
    );

    // If no posts from followed communities, use trending
    if (posts.length === 0) {
      posts = await this.fallbackService.getTrendingPosts(limit);
    }

    // Convert to recommendation format
    return {
      user_id: userId,
      recommendations: posts.map((post, index) => ({
        post_id: post.id,
        score: 1.0 - (index * 0.01), // Decreasing score
        metadata: {
          tags: post.metadata?.tags || [],
          communityId: post.communityId,
        },
      })),
      pagination: {
        total: posts.length,
        limit,
        offset,
        has_more: false,
      },
    };
  }
}
```

---

## Health Checks

Integrate with NestJS health check module:

```bash
npm install @nestjs/terminus
```

Create `src/health/recommendation-health.indicator.ts`:

```typescript
import { Injectable } from '@nestjs/common';
import { HealthIndicator, HealthIndicatorResult, HealthCheckError } from '@nestjs/terminus';
import { RecommendationService } from '../recommendation/recommendation.service';

@Injectable()
export class RecommendationHealthIndicator extends HealthIndicator {
  constructor(
    private readonly recommendationService: RecommendationService,
  ) {
    super();
  }

  async isHealthy(key: string): Promise<HealthIndicatorResult> {
    try {
      const health = await this.recommendationService.checkHealth();

      if (health.status === 'healthy') {
        return this.getStatus(key, true, { details: health });
      }

      throw new HealthCheckError(
        'Recommendation service is unhealthy',
        this.getStatus(key, false, { details: health }),
      );
    } catch (error) {
      throw new HealthCheckError(
        'Recommendation service is unavailable',
        this.getStatus(key, false, { error: error.message }),
      );
    }
  }
}
```

Use in health controller:

```typescript
import { Controller, Get } from '@nestjs/common';
import { HealthCheck, HealthCheckService } from '@nestjs/terminus';
import { RecommendationHealthIndicator } from './recommendation-health.indicator';

@Controller('health')
export class HealthController {
  constructor(
    private health: HealthCheckService,
    private recommendationHealthIndicator: RecommendationHealthIndicator,
  ) {}

  @Get()
  @HealthCheck()
  check() {
    return this.health.check([
      () => this.recommendationHealthIndicator.isHealthy('recommendation'),
    ]);
  }
}
```

---

## Complete Example

### Frontend Integration (React/Next.js)

```typescript
// hooks/useRecommendations.ts
import { useState, useEffect } from 'react';
import axios from 'axios';

interface UseRecommendationsOptions {
  limit?: number;
  enableInfiniteScroll?: boolean;
}

export function useRecommendations(options: UseRecommendationsOptions = {}) {
  const { limit = 20, enableInfiniteScroll = true } = options;
  const [recommendations, setRecommendations] = useState([]);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadMore = async () => {
    if (loading || !hasMore) return;

    setLoading(true);
    setError(null);

    try {
      const response = await axios.get('/api/recommendations', {
        params: { limit, offset },
      });

      const data = response.data;

      setRecommendations((prev) => [...prev, ...data.recommendations]);
      setOffset((prev) => prev + limit);
      setHasMore(data.pagination.has_more);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMore();
  }, []);

  return {
    recommendations,
    loading,
    error,
    hasMore,
    loadMore,
  };
}
```

```typescript
// components/RecommendationFeed.tsx
import React from 'react';
import InfiniteScroll from 'react-infinite-scroll-component';
import { useRecommendations } from '../hooks/useRecommendations';
import PostCard from './PostCard';

export function RecommendationFeed() {
  const { recommendations, loading, error, hasMore, loadMore } = useRecommendations();

  if (error) {
    return <div>Error loading recommendations: {error}</div>;
  }

  return (
    <InfiniteScroll
      dataLength={recommendations.length}
      next={loadMore}
      hasMore={hasMore}
      loader={<h4>Loading...</h4>}
      endMessage={<p>No more recommendations</p>}
    >
      {recommendations.map((rec) => (
        <PostCard key={rec.post_id} postId={rec.post_id} score={rec.score} />
      ))}
    </InfiniteScroll>
  );
}
```

---

## Testing

### Unit Tests

```typescript
// recommendation.service.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { of, throwError } from 'rxjs';
import { RecommendationService } from './recommendation.service';
import { AxiosResponse } from 'axios';

describe('RecommendationService', () => {
  let service: RecommendationService;
  let httpService: HttpService;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RecommendationService,
        {
          provide: HttpService,
          useValue: {
            get: jest.fn(),
            post: jest.fn(),
          },
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string) => {
              if (key === 'recommendation.apiUrl') return 'http://localhost:8000';
              if (key === 'recommendation.timeout') return 5000;
              return null;
            }),
          },
        },
      ],
    }).compile();

    service = module.get<RecommendationService>(RecommendationService);
    httpService = module.get<HttpService>(HttpService);
  });

  it('should fetch recommendations successfully', async () => {
    const mockResponse: AxiosResponse = {
      data: {
        user_id: 'user123',
        recommendations: [
          { post_id: 'post1', score: 0.95, metadata: {} },
        ],
        pagination: {
          total: 100,
          limit: 20,
          offset: 0,
          has_more: true,
        },
      },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {},
    };

    jest.spyOn(httpService, 'get').mockReturnValue(of(mockResponse));

    const result = await service.getUserRecommendations('user123', 20, 0);

    expect(result.user_id).toBe('user123');
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0].post_id).toBe('post1');
  });

  it('should return empty recommendations for user not found', async () => {
    jest.spyOn(httpService, 'get').mockReturnValue(
      throwError(() => ({
        response: { status: 404, data: { detail: 'User not found' } },
      })),
    );

    const result = await service.getUserRecommendations('user999', 20, 0);

    expect(result.recommendations).toHaveLength(0);
    expect(result.pagination.total).toBe(0);
  });
});
```

---

## Best Practices

### 1. **Error Handling**
- Always provide fallback recommendations
- Log errors for monitoring
- Use proper HTTP status codes

### 2. **Caching**
- Cache recommendations for 5-10 minutes
- Invalidate cache after user interactions
- Use stale cache as fallback when API fails

### 3. **Performance**
- Set appropriate timeouts (5 seconds)
- Use connection pooling
- Implement circuit breaker for repeated failures

### 4. **Monitoring**
- Track API response times
- Monitor cache hit rates
- Alert on recommendation service downtime

### 5. **Security**
- Validate user IDs
- Implement rate limiting
- Use authentication for admin endpoints

---

## Deployment Checklist

- [ ] Set up environment variables
- [ ] Configure CORS in FastAPI for your domain
- [ ] Set up health check monitoring
- [ ] Configure caching (Redis recommended)
- [ ] Set up logging and error tracking
- [ ] Test fallback mechanisms
- [ ] Load test recommendation endpoints
- [ ] Set up alerts for service downtime
- [ ] Document API for frontend team
- [ ] Set up automated model retraining

---

## Summary

**Key Integration Points**:

1. **RecommendationService**: Core service that calls FastAPI
2. **RecommendationController**: Exposes endpoints to frontend
3. **Caching**: Redis cache for performance
4. **Fallback**: Trending posts when service fails
5. **Health Checks**: Monitor recommendation service status
6. **Admin Endpoints**: Trigger model reloads

**API Endpoints** (NestJS):

- `GET /recommendations` - Get recommendations for current user
- `GET /recommendations/:userId` - Get recommendations for specific user
- `GET /recommendations/health` - Check service health
- `POST /admin/recommendations/reload` - Reload model
- `GET /admin/recommendations/status` - Get model status

**Next Steps**:

1. Copy service and controller files to your NestJS project
2. Configure environment variables
3. Set up caching (optional but recommended)
4. Implement fallback strategy
5. Test integration
6. Deploy and monitor

For FastAPI documentation, see [README_API.md](README_API.md).
