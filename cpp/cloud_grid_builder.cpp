#include <algorithm>
#include <atomic>
#include <cmath>
#include <cctype>
#include <cstdlib>
#include <dlfcn.h>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace json {

struct Value {
    enum class Kind { Null, Boolean, Number, String, Array, Object };
    Kind kind = Kind::Null;
    bool boolean = false;
    double number = 0.0;
    std::string string;
    std::vector<Value> array;
    std::map<std::string, Value> object;

    const Value& at(const std::string& key) const {
        if (kind != Kind::Object) throw std::runtime_error("expected JSON object");
        auto found = object.find(key);
        if (found == object.end()) throw std::runtime_error("missing JSON field: " + key);
        return found->second;
    }
    double as_number() const {
        if (kind != Kind::Number) throw std::runtime_error("expected JSON number");
        return number;
    }
    int as_int() const { return static_cast<int>(as_number()); }
    bool as_bool() const {
        if (kind != Kind::Boolean) throw std::runtime_error("expected JSON boolean");
        return boolean;
    }
    const std::string& as_string() const {
        if (kind != Kind::String) throw std::runtime_error("expected JSON string");
        return string;
    }
};

class Parser {
  public:
    explicit Parser(std::string source) : source_(std::move(source)) {}

    Value parse() {
        Value result = value();
        whitespace();
        if (position_ != source_.size()) fail("trailing input");
        return result;
    }

  private:
    std::string source_;
    std::size_t position_ = 0;

    [[noreturn]] void fail(const std::string& message) const {
        throw std::runtime_error("JSON parse error at byte " +
                                 std::to_string(position_) + ": " + message);
    }
    void whitespace() {
        while (position_ < source_.size() &&
               std::isspace(static_cast<unsigned char>(source_[position_]))) ++position_;
    }
    char peek() {
        whitespace();
        if (position_ >= source_.size()) fail("unexpected end of input");
        return source_[position_];
    }
    bool consume(char expected) {
        whitespace();
        if (position_ < source_.size() && source_[position_] == expected) {
            ++position_;
            return true;
        }
        return false;
    }
    void expect(char expected) {
        if (!consume(expected)) fail(std::string("expected '") + expected + "'");
    }
    Value value() {
        const char next = peek();
        if (next == '{') return object();
        if (next == '[') return array();
        if (next == '"') {
            Value result; result.kind = Value::Kind::String; result.string = string(); return result;
        }
        if (next == 't') return literal("true", Value::Kind::Boolean, true);
        if (next == 'f') return literal("false", Value::Kind::Boolean, false);
        if (next == 'n') return literal("null", Value::Kind::Null, false);
        return number();
    }
    Value literal(const char* text, Value::Kind kind, bool boolean) {
        std::size_t length = std::char_traits<char>::length(text);
        if (source_.compare(position_, length, text) != 0) fail("invalid literal");
        position_ += length;
        Value result; result.kind = kind; result.boolean = boolean; return result;
    }
    Value number() {
        whitespace();
        const char* begin = source_.c_str() + position_;
        char* end = nullptr;
        const double parsed = std::strtod(begin, &end);
        if (end == begin) fail("invalid number");
        position_ += static_cast<std::size_t>(end - begin);
        Value result; result.kind = Value::Kind::Number; result.number = parsed; return result;
    }
    std::string string() {
        expect('"');
        std::string result;
        while (position_ < source_.size()) {
            char character = source_[position_++];
            if (character == '"') return result;
            if (character != '\\') { result.push_back(character); continue; }
            if (position_ >= source_.size()) fail("unterminated escape");
            char escaped = source_[position_++];
            switch (escaped) {
                case '"': result.push_back('"'); break;
                case '\\': result.push_back('\\'); break;
                case '/': result.push_back('/'); break;
                case 'b': result.push_back('\b'); break;
                case 'f': result.push_back('\f'); break;
                case 'n': result.push_back('\n'); break;
                case 'r': result.push_back('\r'); break;
                case 't': result.push_back('\t'); break;
                default: fail("unsupported string escape");
            }
        }
        fail("unterminated string");
    }
    Value array() {
        Value result; result.kind = Value::Kind::Array;
        expect('[');
        if (consume(']')) return result;
        do { result.array.push_back(value()); } while (consume(','));
        expect(']');
        return result;
    }
    Value object() {
        Value result; result.kind = Value::Kind::Object;
        expect('{');
        if (consume('}')) return result;
        do {
            if (peek() != '"') fail("expected object key");
            std::string key = string();
            expect(':');
            result.object.emplace(std::move(key), value());
        } while (consume(','));
        expect('}');
        return result;
    }
};

}  // namespace json

struct Vec3 { double x, y, z; };

struct BoundaryEdge {
    Vec3 begin, end;
    double sign = 1.0;
    double denominator = 1.0;
};

static Vec3 vec3(const json::Value& value) {
    if (value.kind != json::Value::Kind::Array || value.array.size() != 3)
        throw std::runtime_error("expected a three-number array");
    return {value.array[0].as_number(), value.array[1].as_number(),
            value.array[2].as_number()};
}

static double clamp(double value, double low = 0.0, double high = 1.0) {
    return std::max(low, std::min(high, value));
}

static double smoothstep(double value) {
    value = clamp(value);
    return value * value * (3.0 - 2.0 * value);
}

static double cross_xz(const Vec3& origin, const Vec3& end, const Vec3& point) {
    return ((end.x - origin.x) * (point.z - origin.z)
            - (end.z - origin.z) * (point.x - origin.x));
}

using Noise3 = float (*)(float, float, float, int, int, int, int);

class NativeNoise {
  public:
    NativeNoise(const std::string& python_library, const std::string& perlin_library) {
        python_handle_ = dlopen(python_library.c_str(), RTLD_NOW | RTLD_GLOBAL);
        if (!python_handle_) throw std::runtime_error("cannot load Python library: " + std::string(dlerror()));
        perlin_handle_ = dlopen(perlin_library.c_str(), RTLD_NOW | RTLD_LOCAL);
        if (!perlin_handle_) throw std::runtime_error("cannot load native Perlin library: " + std::string(dlerror()));
        dlerror();
        function_ = reinterpret_cast<Noise3>(dlsym(perlin_handle_, "noise3"));
        const char* error = dlerror();
        if (error) throw std::runtime_error("cannot resolve noise3: " + std::string(error));
    }
    ~NativeNoise() {
        if (perlin_handle_) dlclose(perlin_handle_);
        if (python_handle_) dlclose(python_handle_);
    }
    double fractal(double x, double y, double z, int seed, double octaves,
                   double roughness, double frequency_jump) const {
        int whole = std::max(1, static_cast<int>(octaves));
        double fractional = std::max(0.0, octaves - whole);
        double amplitude = 1.0;
        double result = 0.0;
        for (int octave = 0; octave < whole; ++octave) {
            result += amplitude * function_(static_cast<float>(x), static_cast<float>(y),
                                            static_cast<float>(z), 4096, 4096, 4096, seed);
            x *= frequency_jump; y *= frequency_jump; z *= frequency_jump;
            amplitude *= roughness;
        }
        if (fractional != 0.0)
            result += fractional * amplitude * function_(
                static_cast<float>(x), static_cast<float>(y), static_cast<float>(z),
                4096, 4096, 4096, seed);
        return result;
    }
  private:
    void* python_handle_ = nullptr;
    void* perlin_handle_ = nullptr;
    Noise3 function_ = nullptr;
};

struct Lobe { Vec3 offset; Vec3 radii; double strength; };

class CloudGrid {
  public:
    CloudGrid(const json::Value& root, const NativeNoise& noise) : noise_(noise) {
        if (root.at("contract_version").as_int() != 1)
            throw std::runtime_error("unsupported cloud-grid contract version");
        name_ = root.at("name").as_string();
        medium_name_ = root.at("medium_name").as_string();
        generator_ = root.at("generator").as_string();
        center_ = vec3(root.at("center"));
        dimensions_ = vec3(root.at("dimensions"));
        const auto& resolution = root.at("resolution").array;
        if (resolution.size() != 3) throw std::runtime_error("resolution requires three values");
        nx_ = resolution[0].as_int(); ny_ = resolution[1].as_int(); nz_ = resolution[2].as_int();
        if (nx_ < 2 || ny_ < 2 || nz_ < 2) throw std::runtime_error("resolution values must be at least 2");
        if (dimensions_.x <= 0 || dimensions_.y <= 0 || dimensions_.z <= 0)
            throw std::runtime_error("cloud dimensions must be positive");

        base_min_ = {center_.x - dimensions_.x / 2, center_.y - dimensions_.y / 2,
                     center_.z - dimensions_.z / 2};
        base_max_ = {center_.x + dimensions_.x / 2, center_.y + dimensions_.y / 2,
                     center_.z + dimensions_.z / 2};

        const auto& field = root.at("density_field");
        const auto& shape = field.at("shape");
        bottom_fade_ = shape.at("bottom_fade").as_number();
        top_fade_ = shape.at("top_fade").as_number();
        const auto& noise_config = field.at("noise");
        seed_ = noise_config.at("seed").as_int();
        frequency_ = vec3(noise_config.at("frequency"));
        octaves_ = noise_config.at("octaves").as_number();
        roughness_ = noise_config.at("roughness").as_number();
        frequency_jump_ = noise_config.at("frequency_jump").as_number();
        coverage_ = noise_config.at("coverage").as_number();
        softness_ = noise_config.at("softness").as_number();
        broad_strength_ = noise_config.at("broad_strength").as_number();
        detail_strength_ = noise_config.at("detail_strength").as_number();
        detail_frequency_scale_ = noise_config.at("detail_frequency_scale").as_number();
        const auto& edge_fade = noise_config.at("edge_fade_fraction");
        fade_left_ = edge_fade.at("left").as_number();
        fade_right_ = edge_fade.at("right").as_number();
        fade_bottom_ = edge_fade.at("bottom").as_number();
        fade_top_ = edge_fade.at("top").as_number();
        fade_near_ = edge_fade.at("near").as_number();
        fade_far_ = edge_fade.at("far").as_number();
        edge_influence_ = noise_config.at("edge_influence").as_number();
        density_contrast_ = noise_config.at("density_contrast").as_number();
        modulation_min_ = noise_config.at("density_modulation_min").as_number();
        modulation_max_ = noise_config.at("density_modulation_max").as_number();
        envelope_power_ = noise_config.at("envelope_power").as_number();
        const auto& warp = noise_config.at("domain_warp");
        warp_enabled_ = warp.at("enabled").as_bool();
        warp_frequency_ = vec3(warp.at("frequency"));
        warp_strength_ = vec3(warp.at("strength"));

        const auto& slope = field.at("depth_slope");
        slope_enabled_ = slope.at("enabled").as_bool();
        far_y_offset_ = slope.at("far_y_offset").as_number();
        bounds_min_ = base_min_; bounds_max_ = base_max_;
        if (slope_enabled_) {
            bounds_min_.y += std::min(0.0, far_y_offset_);
            bounds_max_.y += std::max(0.0, far_y_offset_);
        }
        configure_boundary(root.at("boundary"));
        const auto& profile = field.at("depth_profile");
        profile_enabled_ = profile.at("enabled").as_bool();
        full_density_until_z_ = profile.at("full_density_until_z").as_number();
        falloff_distance_ = profile.at("falloff_distance").as_number();
        far_density_scale_ = profile.at("far_density_scale").as_number();

        const auto& lobe_values = field.at("lobes").array;
        for (const auto& value : lobe_values) {
            Lobe lobe{vec3(value.at("center_offset")), vec3(value.at("radii")),
                      value.at("strength").as_number()};
            if (lobe.radii.x <= 0 || lobe.radii.y <= 0 || lobe.radii.z <= 0)
                throw std::runtime_error("lobe radii must be positive");
            lobes_.push_back(lobe);
        }
        if (generator_ == "lobed" && lobes_.empty())
            throw std::runtime_error("lobed cloud requires at least one lobe");
        if (generator_ != "lobed" && generator_ != "mottled_veil")
            throw std::runtime_error("unsupported cloud generator: " + generator_);

        const auto& medium = root.at("medium");
        medium_type_ = medium.at("type").as_string();
        density_scale_ = medium.at("density_scale").as_number();
        sigma_s_ = vec3(medium.at("scattering"));
        sigma_a_ = vec3(medium.at("absorption"));
        anisotropy_ = medium.at("anisotropy").as_number();
        const auto& underside = medium.at("underside");
        underside_enabled_ = underside.at("enabled").as_bool();
        underside_height_fraction_ = underside.at("height_fraction").as_number();
        underside_transition_ = underside.at("transition").as_number();
        underside_scattering_scale_ = underside.at("scattering_scale").as_number();
        underside_absorption_scale_ = underside.at("absorption_scale").as_number();

        if (profile_enabled_ && falloff_distance_ <= 0.0)
            throw std::runtime_error("depth-profile falloff distance must be positive");
        if (far_density_scale_ < 0.0 || far_density_scale_ > 1.0)
            throw std::runtime_error("far density scale must be between 0 and 1");
        if (density_scale_ < 0.0 || sigma_s_.x < 0.0 || sigma_s_.y < 0.0 ||
            sigma_s_.z < 0.0 || sigma_a_.x < 0.0 || sigma_a_.y < 0.0 ||
            sigma_a_.z < 0.0)
            throw std::runtime_error("cloud density and optical values cannot be negative");
        if (anisotropy_ <= -1.0 || anisotropy_ >= 1.0)
            throw std::runtime_error("cloud anisotropy must be between -1 and 1");
        const std::string expected_type = underside_enabled_ ? "rgbgrid" : "uniformgrid";
        if (medium_type_ != expected_type)
            throw std::runtime_error("cloud medium type does not match underside mode");
    }

    std::size_t voxel_count() const {
        return static_cast<std::size_t>(nx_) * ny_ * nz_;
    }

    std::vector<double> build(unsigned requested_threads) const {
        std::vector<double> result(voxel_count());
        unsigned count = requested_threads == 0 ? std::thread::hardware_concurrency() : requested_threads;
        count = std::max(1u, std::min(count, static_cast<unsigned>(result.size())));
        auto worker = [&](std::size_t begin, std::size_t end) {
            for (std::size_t index = begin; index < end; ++index) {
                const int ix = static_cast<int>(index % nx_);
                const std::size_t yz = index / nx_;
                const int iy = static_cast<int>(yz % ny_);
                const int iz = static_cast<int>(yz / ny_);
                const double x = coordinate(bounds_min_.x, bounds_max_.x, ix, nx_);
                const double y = coordinate(bounds_min_.y, bounds_max_.y, iy, ny_);
                const double z = coordinate(bounds_min_.z, bounds_max_.z, iz, nz_);
                result[index] = density(x, y, z);
            }
        };
        std::vector<std::thread> threads;
        std::size_t begin = 0;
        for (unsigned thread = 0; thread < count; ++thread) {
            const std::size_t end = result.size() * (thread + 1) / count;
            threads.emplace_back(worker, begin, end);
            begin = end;
        }
        for (auto& thread : threads) thread.join();
        return result;
    }

    void write(std::ostream& output, const std::vector<double>& density_values) const {
        output << "# Compiled cloud medium: " << name_ << "\n";
        output << "MakeNamedMedium \"" << medium_name_ << "\"\n";
        output << "    \"string type\" [ \"" << medium_type_ << "\" ]\n";
        output << "    \"integer nx\" [ " << nx_ << " ] \"integer ny\" [ " << ny_
               << " ] \"integer nz\" [ " << nz_ << " ]\n";
        output << std::setprecision(17);
        output << "    \"point3 p0\" [ " << bounds_min_.x << ' ' << bounds_min_.y << ' '
               << bounds_min_.z << " ]\n";
        output << "    \"point3 p1\" [ " << bounds_max_.x << ' ' << bounds_max_.y << ' '
               << bounds_max_.z << " ]\n";
        if (underside_enabled_) {
            std::vector<double> absorption, scattering;
            absorption.reserve(density_values.size() * 3);
            scattering.reserve(density_values.size() * 3);
            for (std::size_t index = 0; index < density_values.size(); ++index) {
                const std::size_t yz = index / nx_;
                const int iy = static_cast<int>(yz % ny_);
                const int iz = static_cast<int>(yz / ny_);
                const double y = coordinate(bounds_min_.y, bounds_max_.y, iy, ny_);
                const double z = coordinate(bounds_min_.z, bounds_max_.z, iz, nz_);
                const int ix = static_cast<int>(index % nx_);
                const double x = coordinate(bounds_min_.x, bounds_max_.x, ix, nx_);
                append_optics(density_values[index], x, y, z, absorption, scattering);
            }
            write_values(output, "rgb sigma_a", absorption, 12);
            write_values(output, "rgb sigma_s", scattering, 12);
        } else {
            write_values(output, "float density", density_values, 12);
            output << "    \"rgb sigma_a\" [ " << sigma_a_.x << ' ' << sigma_a_.y << ' '
                   << sigma_a_.z << " ]\n";
            output << "    \"rgb sigma_s\" [ " << sigma_s_.x << ' ' << sigma_s_.y << ' '
                   << sigma_s_.z << " ]\n";
        }
        output << "    \"float g\" [ " << anisotropy_ << " ]\n\n";
    }

  private:
    const NativeNoise& noise_;
    std::string name_, medium_name_, generator_, medium_type_;
    Vec3 center_{}, dimensions_{}, base_min_{}, base_max_{}, bounds_min_{}, bounds_max_{};
    std::string boundary_mode_ = "axis_aligned";
    std::vector<Vec3> bottom_corners_;
    BoundaryEdge boundary_edges_[4];
    double boundary_a_ = 0, boundary_b_ = 0, boundary_c_ = 0,
           boundary_thickness_ = 0, reference_bottom_y_ = 0;
    int nx_ = 0, ny_ = 0, nz_ = 0, seed_ = 0;
    double bottom_fade_ = 0, top_fade_ = 0, octaves_ = 0, roughness_ = 0,
           frequency_jump_ = 0, coverage_ = 0, softness_ = 0, broad_strength_ = 0,
           detail_strength_ = 0, detail_frequency_scale_ = 0, edge_influence_ = 0,
           density_contrast_ = 0, modulation_min_ = 0, modulation_max_ = 0,
           envelope_power_ = 0, far_y_offset_ = 0, full_density_until_z_ = 0,
           falloff_distance_ = 0, far_density_scale_ = 0, density_scale_ = 0,
           anisotropy_ = 0, underside_height_fraction_ = 0,
           underside_transition_ = 0, underside_scattering_scale_ = 0,
           underside_absorption_scale_ = 0, fade_left_ = 0, fade_right_ = 0,
           fade_bottom_ = 0, fade_top_ = 0, fade_near_ = 0, fade_far_ = 0;
    Vec3 frequency_{}, warp_frequency_{}, warp_strength_{}, sigma_s_{}, sigma_a_{};
    bool warp_enabled_ = false, slope_enabled_ = false, profile_enabled_ = false,
         underside_enabled_ = false;
    std::vector<Lobe> lobes_;

    static double coordinate(double low, double high, int index, int count) {
        return low + (high - low) * index / (count - 1);
    }
    void configure_boundary(const json::Value& boundary) {
        boundary_mode_ = boundary.at("mode").as_string();
        if (boundary_mode_ == "axis_aligned") return;
        if (boundary_mode_ != "corner_prism")
            throw std::runtime_error("unsupported cloud boundary mode: " + boundary_mode_);
        if (slope_enabled_)
            throw std::runtime_error("depth_slope must be disabled for corner_prism");
        const auto& corners = boundary.at("bottom_corners");
        const char* names[4] = {"near_left", "near_right", "far_right", "far_left"};
        for (const char* name : names) bottom_corners_.push_back(vec3(corners.at(name)));
        boundary_thickness_ = boundary.at("thickness").as_number();
        if (boundary_thickness_ <= 0.0)
            throw std::runtime_error("corner_prism thickness must be positive");

        const Vec3& p0 = bottom_corners_[0];
        const Vec3& p1 = bottom_corners_[1];
        const Vec3& p2 = bottom_corners_[2];
        const Vec3& p3 = bottom_corners_[3];
        const double determinant = ((p1.x - p0.x) * (p2.z - p0.z)
                                    - (p2.x - p0.x) * (p1.z - p0.z));
        if (std::abs(determinant) <= 1e-12)
            throw std::runtime_error("corner_prism footprint has zero area");
        boundary_b_ = (((p1.y - p0.y) * (p2.z - p0.z)
                        - (p2.y - p0.y) * (p1.z - p0.z)) / determinant);
        boundary_c_ = (((p1.x - p0.x) * (p2.y - p0.y)
                        - (p2.x - p0.x) * (p1.y - p0.y)) / determinant);
        boundary_a_ = p0.y - boundary_b_ * p0.x - boundary_c_ * p0.z;
        const double scale = std::max(
            {std::abs(p0.x) + std::abs(p0.z), std::abs(p1.x) + std::abs(p1.z),
             std::abs(p2.x) + std::abs(p2.z), std::abs(p3.x) + std::abs(p3.z), 1.0});
        const double plane_tolerance = std::max(
            {1e-6, boundary_thickness_ * 1e-8, scale * 1e-8});
        if (std::abs(boundary_a_ + boundary_b_ * p3.x + boundary_c_ * p3.z - p3.y)
            > plane_tolerance)
            throw std::runtime_error("corner_prism bottom corners must be coplanar");

        Vec3 centroid{};
        for (const Vec3& point : bottom_corners_) {
            centroid.x += point.x / 4.0;
            centroid.y += point.y / 4.0;
            centroid.z += point.z / 4.0;
        }
        reference_bottom_y_ = centroid.y;
        const int edge_indices[4][2] = {{0, 1}, {1, 2}, {2, 3}, {3, 0}};
        double turn_sign = 0.0;
        for (int index = 0; index < 4; ++index) {
            const Vec3& begin = bottom_corners_[edge_indices[index][0]];
            const Vec3& end = bottom_corners_[edge_indices[index][1]];
            const Vec3& next = bottom_corners_[edge_indices[(index + 1) % 4][1]];
            const double turn = cross_xz(begin, end, next);
            if (std::abs(turn) <= 1e-12 || (turn_sign != 0.0 && turn * turn_sign < 0.0))
                throw std::runtime_error(
                    "corner_prism bottom corners must form a non-crossing convex footprint");
            turn_sign = turn;
            const double interior = cross_xz(begin, end, centroid);
            const double sign = interior > 0.0 ? 1.0 : -1.0;
            double denominator = 0.0;
            for (const Vec3& point : bottom_corners_)
                denominator = std::max(denominator, sign * cross_xz(begin, end, point));
            boundary_edges_[index] = {begin, end, sign, denominator};
        }

        bounds_min_ = {bottom_corners_[0].x, bottom_corners_[0].y,
                       bottom_corners_[0].z};
        bounds_max_ = bounds_min_;
        for (const Vec3& point : bottom_corners_) {
            bounds_min_.x = std::min(bounds_min_.x, point.x);
            bounds_min_.y = std::min(bounds_min_.y, point.y);
            bounds_min_.z = std::min(bounds_min_.z, point.z);
            bounds_max_.x = std::max(bounds_max_.x, point.x);
            bounds_max_.y = std::max(bounds_max_.y, point.y + boundary_thickness_);
            bounds_max_.z = std::max(bounds_max_.z, point.z);
        }
        base_min_ = bounds_min_;
        base_max_ = bounds_max_;
    }
    double boundary_bottom(double x, double z) const {
        return boundary_a_ + boundary_b_ * x + boundary_c_ * z;
    }
    bool boundary_coordinates(double x, double y, double z, double result[6]) const {
        // result order: left, right, bottom, top, near, far
        const Vec3 point{x, y, z};
        const int result_indices[4] = {4, 1, 5, 0}; // near, right, far, left
        for (int edge = 0; edge < 4; ++edge) {
            const auto& item = boundary_edges_[edge];
            const double value = item.sign * cross_xz(item.begin, item.end, point)
                                 / item.denominator;
            if (value < -1e-9) return false;
            result[result_indices[edge]] = value;
        }
        const double vertical = (y - boundary_bottom(x, z)) / boundary_thickness_;
        if (vertical < -1e-9 || vertical > 1.0 + 1e-9) return false;
        result[2] = vertical;
        result[3] = 1.0 - vertical;
        return true;
    }
    double fractal(double x, double y, double z, int seed) const {
        return noise_.fractal(x, y, z, seed, octaves_, roughness_, frequency_jump_);
    }
    double slope_offset(double z) const {
        if (!slope_enabled_) return 0.0;
        double fraction = clamp((base_max_.z - z) /
                                std::max(base_max_.z - base_min_.z, 1e-9));
        return fraction * far_y_offset_;
    }
    double depth_weight(double z) const {
        if (!profile_enabled_) return 1.0;
        double beyond = std::max(0.0, full_density_until_z_ - z);
        return std::max(far_density_scale_, std::exp(-beyond / falloff_distance_));
    }
    double envelope(double x, double y, double z) const {
        double combined = 0.0;
        for (const auto& lobe : lobes_) {
            const double dx = (x - (center_.x + lobe.offset.x)) / lobe.radii.x;
            const double dy = (y - (center_.y + lobe.offset.y)) / lobe.radii.y;
            const double dz = (z - (center_.z + lobe.offset.z)) / lobe.radii.z;
            double influence = clamp(smoothstep(1.0 - std::sqrt(dx*dx + dy*dy + dz*dz)) *
                                     lobe.strength);
            combined = 1.0 - (1.0 - combined) * (1.0 - influence);
        }
        return combined;
    }
    double density(double x, double y, double z) const {
        double local[6]{};
        const bool corner_prism = boundary_mode_ == "corner_prism";
        if (corner_prism && !boundary_coordinates(x, y, z, local)) return 0.0;
        if (generator_ == "mottled_veil") {
            const double reference_y = corner_prism
                ? y - (boundary_bottom(x, z) - reference_bottom_y_)
                : y - slope_offset(z);
            const double primary = fractal(x * frequency_.x, reference_y * frequency_.y,
                                           z * frequency_.z, seed_);
            const double detail = fractal(x * frequency_.x * detail_frequency_scale_,
                                          reference_y * frequency_.y * detail_frequency_scale_,
                                          z * frequency_.z * detail_frequency_scale_, seed_ + 401);
            const double field = 0.5 + broad_strength_ * primary + detail_strength_ * detail;
            const double mottle = smoothstep((field - coverage_) / std::max(softness_, 1e-6));
            double edge_weight = 1.0;
            const double face_fades[6] = {fade_left_, fade_right_, fade_bottom_,
                                          fade_top_, fade_near_, fade_far_};
            if (corner_prism) {
                for (int face = 0; face < 6; ++face)
                    if (face_fades[face] > 0.0)
                        edge_weight *= smoothstep(local[face] / face_fades[face]);
            } else {
                const double coordinates[3] = {x, reference_y, z};
                const double minimums[3] = {base_min_.x, base_min_.y, base_min_.z};
                const double maximums[3] = {base_max_.x, base_max_.y, base_max_.z};
                const double low_fades[3] = {fade_left_, fade_bottom_, fade_far_};
                const double high_fades[3] = {fade_right_, fade_top_, fade_near_};
                for (int axis = 0; axis < 3; ++axis) {
                    const double normalized = (coordinates[axis] - minimums[axis]) /
                                              (maximums[axis] - minimums[axis]);
                    edge_weight *= smoothstep(normalized / std::max(low_fades[axis], 1e-6));
                    edge_weight *= smoothstep((1.0 - normalized) /
                                              std::max(high_fades[axis], 1e-6));
                }
            }
            return clamp(density_scale_ * mottle * edge_weight * depth_weight(z),
                         0.0, density_scale_);
        }

        double wx = x, wy = y, wz = z;
        if (warp_enabled_) {
            const double warp_x = fractal(x * warp_frequency_.x, y * warp_frequency_.y,
                                          z * warp_frequency_.z, seed_ + 101);
            const double warp_y = fractal(x * warp_frequency_.x, y * warp_frequency_.y,
                                          z * warp_frequency_.z, seed_ + 211);
            wx += warp_strength_.x * warp_x;
            wy += warp_strength_.y * warp_y;
            wz += warp_strength_.z * (0.55 * warp_x - 0.45 * warp_y);
        }
        const double body = envelope(wx, wy, wz);
        if (body <= 0.0) return 0.0;
        const double bottom_y = corner_prism ? boundary_bottom(x, z) : bounds_min_.y;
        const double top_y = corner_prism ? bottom_y + boundary_thickness_ : bounds_max_.y;
        const double bottom = smoothstep((y - bottom_y) / std::max(bottom_fade_, 1e-9));
        const double top = smoothstep((top_y - y) / std::max(top_fade_, 1e-9));
        const double density_noise = fractal(wx * frequency_.x, wy * frequency_.y,
                                             wz * frequency_.z, seed_ + 307);
        const double support = smoothstep(
            (body + edge_influence_ * density_noise - coverage_) / std::max(softness_, 1e-6));
        const double modulation = clamp(1.0 + density_contrast_ * density_noise,
                                        modulation_min_, modulation_max_);
        const double result = density_scale_ * support *
                              std::pow(body, std::max(envelope_power_, 1e-6)) *
                              modulation * bottom * top;
        return clamp(result, 0.0, density_scale_);
    }
    void append_optics(double density_value, double x, double y, double z,
                       std::vector<double>& absorption,
                       std::vector<double>& scattering) const {
        const double normalized_y = boundary_mode_ == "corner_prism"
            ? (y - boundary_bottom(x, z)) / boundary_thickness_
            : (y - slope_offset(z) - base_min_.y) /
              std::max(base_max_.y - base_min_.y, 1e-9);
        const double transition_start = underside_height_fraction_ -
                                        0.5 * underside_transition_;
        const double underside_weight = 1.0 - smoothstep(
            (normalized_y - transition_start) / std::max(underside_transition_, 1e-6));
        const double scatter_factor = 1.0 + underside_weight *
                                      (underside_scattering_scale_ - 1.0);
        const double absorb_factor = 1.0 + underside_weight *
                                     (underside_absorption_scale_ - 1.0);
        absorption.insert(absorption.end(), {
            density_value * absorb_factor * sigma_a_.x,
            density_value * absorb_factor * sigma_a_.y,
            density_value * absorb_factor * sigma_a_.z});
        scattering.insert(scattering.end(), {
            density_value * scatter_factor * sigma_s_.x,
            density_value * scatter_factor * sigma_s_.y,
            density_value * scatter_factor * sigma_s_.z});
    }
    static void write_values(std::ostream& output, const std::string& type,
                             const std::vector<double>& values, int per_line) {
        output << "    \"" << type << "\" [\n" << std::fixed << std::setprecision(5);
        for (std::size_t index = 0; index < values.size(); ++index) {
            if (index % per_line == 0) output << "        ";
            output << values[index];
            if (index % per_line == static_cast<std::size_t>(per_line - 1) ||
                index + 1 == values.size()) output << '\n';
            else output << ' ';
        }
        output << "    ]\n" << std::defaultfloat << std::setprecision(17);
    }
};

struct Arguments {
    std::string spec, output, python_library, perlin_library;
    unsigned threads = 1;
};

static Arguments arguments(int argc, char** argv) {
    Arguments result;
    for (int index = 1; index < argc; ++index) {
        const std::string option = argv[index];
        if (index + 1 >= argc) throw std::runtime_error("missing value for " + option);
        const std::string value = argv[++index];
        if (option == "--spec") result.spec = value;
        else if (option == "--output") result.output = value;
        else if (option == "--threads") {
            if (!value.empty() && value.front() == '-')
                throw std::runtime_error("thread count cannot be negative");
            result.threads = static_cast<unsigned>(std::stoul(value));
            if (result.threads > 256)
                throw std::runtime_error("thread count cannot exceed 256");
        }
        else if (option == "--python-library") result.python_library = value;
        else if (option == "--perlin-library") result.perlin_library = value;
        else throw std::runtime_error("unknown option: " + option);
    }
    if (result.spec.empty() || result.output.empty() || result.python_library.empty() ||
        result.perlin_library.empty())
        throw std::runtime_error(
            "usage: cloud_grid_builder --spec JOB --output MEDIUM --threads N "
            "--python-library LIB --perlin-library LIB");
    return result;
}

int main(int argc, char** argv) {
    try {
        const Arguments options = arguments(argc, argv);
        std::ifstream input(options.spec);
        if (!input) throw std::runtime_error("cannot open job specification: " + options.spec);
        const std::string source((std::istreambuf_iterator<char>(input)),
                                 std::istreambuf_iterator<char>());
        const json::Value root = json::Parser(source).parse();
        const NativeNoise noise(options.python_library, options.perlin_library);
        const CloudGrid grid(root, noise);
        const std::vector<double> density = grid.build(options.threads);
        std::ofstream output(options.output);
        if (!output) throw std::runtime_error("cannot create output: " + options.output);
        grid.write(output, density);
        if (!output) throw std::runtime_error("failed while writing output: " + options.output);
        const unsigned reported_threads = options.threads == 0
            ? std::max(1u, std::thread::hardware_concurrency())
            : options.threads;
        std::cerr << "cloud_grid_builder: wrote " << density.size() << " voxels using "
                  << reported_threads
                  << " thread(s)\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "cloud_grid_builder: ERROR: " << error.what() << '\n';
        return 1;
    }
}
