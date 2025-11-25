import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AdSpace } from './ad-space.component';

describe('AdSpace', () => {
  let component: AdSpace;
  let fixture: ComponentFixture<AdSpace>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AdSpace]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AdSpace);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
