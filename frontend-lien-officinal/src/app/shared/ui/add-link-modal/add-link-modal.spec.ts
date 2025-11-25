import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AddLinkModal } from './add-link-modal.component';

describe('AddLinkModal', () => {
  let component: AddLinkModal;
  let fixture: ComponentFixture<AddLinkModal>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AddLinkModal]
    })
    .compileComponents();

    fixture = TestBed.createComponent(AddLinkModal);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
