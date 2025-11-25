import { ComponentFixture, TestBed } from '@angular/core/testing';

import { PinPad } from './pin-pad.component';

describe('PinPad', () => {
  let component: PinPad;
  let fixture: ComponentFixture<PinPad>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [PinPad]
    })
    .compileComponents();

    fixture = TestBed.createComponent(PinPad);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
