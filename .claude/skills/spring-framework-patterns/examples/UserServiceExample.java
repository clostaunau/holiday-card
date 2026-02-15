package com.example.app.service;

import com.example.app.dto.CreateUserRequest;
import com.example.app.dto.UpdateUserRequest;
import com.example.app.dto.UserDTO;
import com.example.app.entity.User;
import com.example.app.exception.EmailAlreadyExistsException;
import com.example.app.exception.ResourceNotFoundException;
import com.example.app.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.Optional;

/**
 * Example service implementation demonstrating Spring best practices.
 *
 * Key features demonstrated:
 * - Constructor injection with Lombok @RequiredArgsConstructor
 * - @Transactional for transaction management
 * - Read-only optimization for queries
 * - Proper exception handling
 * - Logging with SLF4J
 * - Entity-DTO mapping
 * - Business validation
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class UserService {

    // Dependencies injected via constructor (final fields)
    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailService emailService;

    /**
     * Find all users with pagination.
     * Uses @Transactional(readOnly = true) for optimization.
     */
    @Transactional(readOnly = true)
    public Page<UserDTO> findAll(Pageable pageable) {
        log.debug("Finding all users with pagination: {}", pageable);
        return userRepository.findAll(pageable)
                .map(this::mapToDTO);
    }

    /**
     * Find user by ID.
     */
    @Transactional(readOnly = true)
    public Optional<UserDTO> findById(Long id) {
        log.debug("Finding user by id: {}", id);
        return userRepository.findById(id)
                .map(this::mapToDTO);
    }

    /**
     * Create new user.
     * Demonstrates:
     * - Business validation
     * - Password encoding
     * - Event publishing (email)
     * - Transaction management
     */
    @Transactional
    public UserDTO createUser(CreateUserRequest request) {
        log.info("Creating new user: {}", request.getEmail());

        // Business validation
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new EmailAlreadyExistsException(request.getEmail());
        }

        // Create entity
        User user = new User();
        user.setEmail(request.getEmail());
        user.setName(request.getName());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setActive(true);
        user.setCreatedAt(LocalDateTime.now());

        // Save
        User saved = userRepository.save(user);
        log.info("User created with id: {}", saved.getId());

        // Send welcome email (async - won't rollback transaction if fails)
        emailService.sendWelcomeEmailAsync(saved);

        return mapToDTO(saved);
    }

    /**
     * Update existing user.
     */
    @Transactional
    public Optional<UserDTO> updateUser(Long id, UpdateUserRequest request) {
        log.info("Updating user with id: {}", id);

        return userRepository.findById(id)
                .map(user -> {
                    // Update fields
                    if (request.getName() != null) {
                        user.setName(request.getName());
                    }
                    if (request.getEmail() != null && !request.getEmail().equals(user.getEmail())) {
                        // Validate new email is not taken
                        if (userRepository.existsByEmail(request.getEmail())) {
                            throw new EmailAlreadyExistsException(request.getEmail());
                        }
                        user.setEmail(request.getEmail());
                    }

                    User updated = userRepository.save(user);
                    log.info("User updated: {}", id);
                    return mapToDTO(updated);
                });
    }

    /**
     * Delete user.
     * Throws exception if user doesn't exist.
     */
    @Transactional
    public void deleteUser(Long id) {
        log.info("Deleting user with id: {}", id);

        if (!userRepository.existsById(id)) {
            throw new ResourceNotFoundException("User", id);
        }

        userRepository.deleteById(id);
        log.info("User deleted: {}", id);
    }

    /**
     * Map entity to DTO.
     * In production, consider using MapStruct for this.
     */
    private UserDTO mapToDTO(User user) {
        UserDTO dto = new UserDTO();
        dto.setId(user.getId());
        dto.setEmail(user.getEmail());
        dto.setName(user.getName());
        dto.setCreatedAt(user.getCreatedAt());
        dto.setActive(user.isActive());
        // Don't include password in DTO!
        return dto;
    }
}
