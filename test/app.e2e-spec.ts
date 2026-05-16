import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import request from 'supertest';
import { App } from 'supertest/types';
import { AppModule } from './../src/app.module';

describe('AppController (e2e)', () => {
  let app: INestApplication<App>;

  beforeEach(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    await app.init();
  });

  it('/ (GET)', () => {
    return request(app.getHttpServer())
      .get('/')
      .expect(200)
      .expect('Hello World!');
  });

  describe('/comexstat/partners (GET)', () => {
    it('should return different results for different custom periods', async () => {
      const response1 = await request(app.getHttpServer())
        .get('/comexstat/partners')
        .query({
          period: 'custom',
          'customPeriod[from]': '2010-03',
          'customPeriod[to]': '2010-05',
          flow: 'export',
          topN: 3,
        })
        .expect(200);

      expect(response1.body.success).toBe(true);
      expect(response1.body.data).toBeDefined();
      expect(Array.isArray(response1.body.data)).toBe(true);

      const response2 = await request(app.getHttpServer())
        .get('/comexstat/partners')
        .query({
          period: 'custom',
          'customPeriod[from]': '2010-07',
          'customPeriod[to]': '2010-09',
          flow: 'export',
          topN: 3,
        })
        .expect(200);

      expect(response2.body.success).toBe(true);
      expect(response2.body.data).toBeDefined();
      expect(Array.isArray(response2.body.data)).toBe(true);

      // Verify that the results are different
      const firstCountry1 = response1.body.data[0];
      const firstCountry2 = response2.body.data[0];

      console.log('Period 2010-03 to 2010-05:', firstCountry1);
      console.log('Period 2010-07 to 2010-09:', firstCountry2);

      // The export values should be different for different periods
      if (firstCountry1 && firstCountry2 && firstCountry1.exports && firstCountry2.exports) {
        expect(firstCountry1.exports).not.toBe(firstCountry2.exports);
      }
    }, 30000);
  });
});
