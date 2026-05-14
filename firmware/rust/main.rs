#![no_std]
#![no_main]

use core::ffi::c_char;

unsafe extern "C" {
    fn PanicDisplayRenderText(message: *const c_char);
}

#[unsafe(no_mangle)]
pub extern "C" fn main() -> ! {
    static MESSAGE: &[u8] = b"Hello from Rust!\0";

    // SAFETY: MESSAGE is a static null-terminated C string.
    unsafe { PanicDisplayRenderText(MESSAGE.as_ptr().cast()) };

    loop {
        core::hint::spin_loop();
    }
}

#[panic_handler]
fn panic(_info: &core::panic::PanicInfo<'_>) -> ! {
    loop {
        core::hint::spin_loop();
    }
}
